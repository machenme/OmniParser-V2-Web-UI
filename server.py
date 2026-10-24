import base64
import binascii
import io
import json
import math
import re
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'third_party/omniparser'))
from util import utils
from util.yolov9 import YOLOv9Detector

PORT = 17897
MAX_BODY = 24 * 1024 * 1024
OUTPUT = ROOT / 'output'
OUTPUT.mkdir(exist_ok=True)
HISTORY = OUTPUT / 'history'
HISTORY.mkdir(exist_ok=True)
HISTORY_ID = r'[0-9]{8}-[0-9]{6}-[0-9]{6}-[0-9a-f]{32}'
lock = threading.Lock()
history_lock = threading.Lock()
history_records = {}
caption_model_processor = None


def history_summary(result):
    return {key: result[key] for key in (
        'history_id', 'created_at', 'width', 'height',
        'source_url', 'image_url', 'thumbnail_url',
    )} | {'element_count': len(result['elements'])}


for metadata_path in HISTORY.glob('*.json'):
    if not re.fullmatch(HISTORY_ID + r'\.json', metadata_path.name):
        continue
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata['history_id'] != metadata_path.stem:
            continue
        history_records[metadata_path.stem] = history_summary(metadata)
    except (OSError, ValueError, KeyError, TypeError):
        continue


PARAMETERS = {
    'box_threshold': ('图标置信度', 0.05, 0.01, 1.0),
    'iou_threshold': ('重叠去重阈值', 0.7, 0.01, 1.0),
    'imgsz': ('图标检测尺寸', 1280, 640, 1920),
    'text_threshold': ('文字检测阈值', 0.7, 0.1, 1.0),
    'width_ths': ('文字合并间距', 1.0, 0.1, 3.0),
    'mag_ratio': ('小字检测放大倍率', 1.0, 1.0, 3.0),
}

# 封闭标签集：只放下游真正需要判断的可操作元素。每个标签必须是单 token，
# 否则首 token logits 读法无法把它们放进同一个分布比较，加载时直接报错。
ICON_CROP_SIZE = 64

ICON_LABELS = (
    'search', 'settings', 'close', 'file', 'add', 'delete',
    'menu', 'edit', 'share', 'download', 'user', 'star',
    'lock', 'mail', 'camera', 'minus', 'arrow', 'check',
    'warning', 'image', 'play', 'pause', 'home', 'back',
)


def validate_parameters(parameters):
    if not isinstance(parameters, dict):
        raise ValueError('parameters 必须是参数对象。')
    if parameters.keys() - (PARAMETERS.keys() | {'icon_caption', 'icon_label'}):
        raise ValueError('包含不支持的识别参数。')
    values = {}
    for name, (label, default, minimum, maximum) in PARAMETERS.items():
        value = parameters.get(name, default)
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not minimum <= value <= maximum):
            raise ValueError(f'{label}必须在 {minimum} 至 {maximum} 之间。')
        if name == 'imgsz':
            if value % 32:
                raise ValueError('图标检测尺寸必须是 32 的倍数。')
            value = int(value)
        values[name] = value
    icon_caption = parameters.get('icon_caption', False)
    if type(icon_caption) is not bool:
        raise ValueError('图标语义描述必须是布尔值。')
    icon_label = parameters.get('icon_label', False)
    if type(icon_label) is not bool:
        raise ValueError('图标分类描述必须是布尔值。')
    if icon_caption and icon_label:
        raise ValueError('图标语义描述和图标分类描述不能同时开启。')
    values['icon_caption'] = icon_caption
    values['icon_label'] = icon_label
    return values


def get_caption_model():
    global caption_model_processor
    if caption_model_processor is None:
        from transformers import AutoModelForCausalLM, AutoProcessor

        path = ROOT / 'models/icon_caption'
        if not (path / 'model.safetensors').is_file():
            raise ValueError('请先运行 scripts/download_models.py --caption 下载图标语义模型。')
        processor = AutoProcessor.from_pretrained(
            path, trust_remote_code=True, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            path, torch_dtype=torch.float16, trust_remote_code=True,
            local_files_only=True, attn_implementation='eager').to('cuda').eval()
        caption_model_processor = {'model': model, 'processor': processor}
    return caption_model_processor


def build_label_tokens(processor, labels=ICON_LABELS):
    tokenizer = processor.tokenizer
    entries = []
    for label in labels:
        plain = tokenizer.encode(label, add_special_tokens=False)
        spaced = tokenizer.encode(' ' + label, add_special_tokens=False)
        if len(plain) != 1 or len(spaced) != 1:
            raise ValueError(f'封闭标签 {label!r} 不是单 token，无法用首 token 读取。')
        entries.append((label, plain[0], spaced[0]))
    return entries


def classify_icons(image, boxes, entries, batch_size=16):
    # 只解码到首个内容 token：第 0 步输出解码器起始符，第 1 步才是候选标签的分布
    # 位置。相比自由描述最多 20 步，省掉大部分解码。
    caption_model_processor = get_caption_model()
    model = caption_model_processor['model']
    processor = caption_model_processor['processor']
    to_pil = utils.ToPILImage()
    pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    flat_ids = torch.tensor([token for _, plain, spaced in entries
                             for token in (plain, spaced)], device='cuda')
    results = []
    with torch.inference_mode():
        for start in range(0, len(boxes), batch_size):
            crops = []
            for box in boxes[start:start + batch_size]:
                xmin = max(0, min(width - 1, int(box[0] * width)))
                ymin = max(0, min(height - 1, int(box[1] * height)))
                xmax = max(xmin + 1, min(width, int(box[2] * width)))
                ymax = max(ymin + 1, min(height, int(box[3] * height)))
                crop = pixels[ymin:ymax, xmin:xmax, :]
                # 与上游描述流程一致：统一到 64×64，否则不同尺寸的裁剪无法组成一个批次。
                crop = utils.cv2.resize(np.ascontiguousarray(crop), (ICON_CROP_SIZE, ICON_CROP_SIZE))
                crops.append(to_pil(crop))
            inputs = processor(images=crops, text=['<CAPTION>'] * len(crops),
                               return_tensors='pt', do_resize=False)
            inputs = inputs.to(device='cuda', dtype=torch.float16)
            generated = model.generate(
                input_ids=inputs['input_ids'], pixel_values=inputs['pixel_values'],
                max_new_tokens=3, num_beams=1, do_sample=False,
                output_scores=True, return_dict_in_generate=True)
            # max_new_tokens=2 时序列刚够两个位置就会被当成已结束，scores[1] 全是
            # 遮蔽值；3 才能稳定拿到首个内容 token 的分布。
            logits = generated.scores[1].float()
            scores = logits[:, flat_ids].reshape(len(crops), len(entries), 2).max(dim=2).values
            weights = torch.softmax(scores, dim=-1)
            for index in range(len(crops)):
                best = int(scores[index].argmax())
                # 候选集内 softmax 只是相对参考，不是校准后的置信度。
                results.append((entries[best][0], round(float(weights[index, best]), 3)))
    return results


def parse_image(encoded, parameters):
    try:
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 20_000_000:
                raise ValueError('图片不能超过 2000 万像素。')
            image = source.convert('RGB')
    except (binascii.Error, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('请提供有效的图片。') from exc
    started = time.perf_counter()
    with lock, torch.inference_mode():
        (text, boxes), _ = utils.check_ocr_box(
            image, display_img=False, output_bb_format='xyxy',
            easyocr_args={'text_threshold': parameters['text_threshold'],
                          'paragraph': False, 'batch_size': 8,
                          'width_ths': parameters['width_ths'],
                          'mag_ratio': parameters['mag_ratio']},
        )
        marked, _, elements = utils.get_som_labeled_img(
            image, detector, BOX_TRESHOLD=parameters['box_threshold'], ocr_bbox=boxes,
            ocr_text=text, use_local_semantics=False,
            iou_threshold=parameters['iou_threshold'],
            scale_img=True, imgsz=parameters['imgsz'],
            draw_bbox_config={'text_scale': 0.45, 'text_padding': 3,
                              'text_thickness': 1, 'thickness': 2},
        )
        if parameters['icon_caption']:
            icons = [element for element in elements
                     if element['type'] == 'icon' and element['content'] is None]
            if icons:
                captions = utils.get_parsed_content_icon(
                    torch.tensor([element['bbox'] for element in icons]), 0,
                    np.asarray(image), get_caption_model(), prompt='<CAPTION>', batch_size=16)
                for element, caption in zip(icons, captions, strict=True):
                    element['content'] = caption
                    element['source'] = 'box_yolo_content_caption'
        if parameters['icon_label']:
            icons = [element for element in elements
                     if element['type'] == 'icon' and element['content'] is None]
            if icons:
                entries = build_label_tokens(get_caption_model()['processor'])
                labeled = classify_icons(image, [element['bbox'] for element in icons], entries)
                for element, (label, score) in zip(icons, labeled, strict=True):
                    element['content'] = label
                    element['confidence'] = score
                    element['source'] = 'box_yolo_content_label'
        for index, element in enumerate(elements, start=1):
            element['id'] = index
        created = datetime.now().astimezone()
        history_id = created.strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid4().hex
        result = {'image_base64': marked, 'elements': elements,
                  'width': image.width, 'height': image.height,
                  'parameters': parameters,
                  'seconds': round(time.perf_counter() - started, 2),
                  'history_id': history_id, 'created_at': created.isoformat(),
                  'source_url': f'/history/{history_id}/source.png',
                  'image_url': f'/history/{history_id}/marked.png',
                  'thumbnail_url': f'/history/{history_id}/thumbnail.png'}
        marked_bytes = base64.b64decode(marked)
        image.save(HISTORY / f'{history_id}-source.png', format='PNG')
        (HISTORY / f'{history_id}-marked.png').write_bytes(marked_bytes)
        thumbnail = image.copy()
        thumbnail.thumbnail((160, 100), Image.Resampling.LANCZOS)
        thumbnail.save(HISTORY / f'{history_id}-thumbnail.png', format='PNG')
        metadata_json = json.dumps(
            {k: v for k, v in result.items() if k != 'image_base64'},
            ensure_ascii=False, indent=2)
        (OUTPUT / 'latest.png').write_bytes(marked_bytes)
        (OUTPUT / 'latest.json').write_text(metadata_json, encoding='utf-8')
        temporary_path = HISTORY / f'{history_id}.json.tmp'
        temporary_path.write_text(metadata_json, encoding='utf-8')
        temporary_path.replace(HISTORY / f'{history_id}.json')
        with history_lock:
            history_records[history_id] = history_summary(result)
    return result


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, content_type='application/json; charset=utf-8'):
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            self.send(403, {'error': '仅允许本机访问。'})
        elif self.path == '/probe/':
            self.send(200, {'ready': True, 'gpu': torch.cuda.get_device_name(0)})
        elif self.path == '/':
            self.send(200, (ROOT / 'web/index.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/history/':
            with history_lock:
                records = [history_records[key] for key in sorted(history_records, reverse=True)]
            self.send(200, {'latest_id': records[0]['history_id'] if records else None,
                            'records': records})
        elif match := re.fullmatch(
                rf'/history/({HISTORY_ID})/(result\.json|source\.png|marked\.png|thumbnail\.png)',
                self.path):
            history_id, resource = match.groups()
            metadata_path = HISTORY / f'{history_id}.json'
            path = (metadata_path if resource == 'result.json'
                    else HISTORY / f'{history_id}-{resource}')
            try:
                if not metadata_path.is_file():
                    raise FileNotFoundError
                data = path.read_bytes()
            except FileNotFoundError:
                self.send(404, {'error': '历史记录不存在。'})
            else:
                content_type = ('application/json; charset=utf-8' if resource == 'result.json'
                                else 'image/png')
                self.send(200, data, content_type)
        else:
            self.send(404, {'error': '页面不存在。'})

    def do_POST(self):
        origin = self.headers.get('Origin')
        allowed = (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}')
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}') or (origin and origin not in allowed):
            self.send(403, {'error': '仅允许本机调用。'})
            return
        if self.path != '/parse/':
            self.send(404, {'error': '接口不存在。'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send(415, {'error': '请求必须使用 application/json。'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                self.send(413, {'error': '图片请求过大或为空。'})
                return
            body = json.loads(self.rfile.read(length))
            encoded = body.get('image_base64') if isinstance(body, dict) else None
            if not isinstance(encoded, str):
                raise ValueError('缺少 image_base64 图片字段。')
            parameters = validate_parameters(body.get('parameters', {}))
            result = parse_image(encoded, parameters)
        except (ValueError, UnicodeError) as exc:
            self.send(400, {'error': str(exc)})
        except Exception:
            import traceback
            traceback.print_exc()
            self.send(500, {'error': '解析失败，请查看 logs/server-error.log。'})
        else:
            self.send(200, result)


if __name__ == '__main__':
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA 不可用，请检查 NVIDIA 驱动和 PyTorch 安装。')
    detector = YOLOv9Detector(ROOT / 'models/icon_detect_v3/model.pt', device='cuda')
    utils.reader = __import__('easyocr').Reader(
        ['ch_sim', 'en'], gpu=True,
        model_storage_directory=str(ROOT / 'models/ocr'), download_enabled=False,
    )
    with torch.inference_mode():
        detector.predict(Image.new('RGB', (640, 640), 'white'))
        utils.reader.readtext(np.full((128, 256, 3), 255, dtype=np.uint8))
    print(f'本地服务已就绪：http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
