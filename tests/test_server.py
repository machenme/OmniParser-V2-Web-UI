import base64
import io
import json
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:17897'
session = requests.Session()
session.trust_env = False


def encode(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


class ServerTests(unittest.TestCase):
    def parse(self, image, parameters=None):
        payload = {'image_base64': encode(image)}
        if parameters is not None:
            payload['parameters'] = parameters
        response = session.post(URL + '/parse/', json=payload, timeout=180)
        self.assertEqual(response.status_code, 200, response.text[:500])
        result = response.json()
        marked = Image.open(io.BytesIO(base64.b64decode(result['image_base64'])))
        self.assertEqual(marked.size, image.size)
        for index, element in enumerate(result['elements'], start=1):
            self.assertEqual(element['id'], index)
            self.assertEqual(len(element['bbox']), 4)
            self.assertTrue(all(0 <= value <= 1 for value in element['bbox']))
        self.assertEqual((result['width'], result['height']), image.size)
        history_id = result['history_id']
        self.assertRegex(history_id, r'^[0-9]{8}-[0-9]{6}-[0-9]{6}-[0-9a-f]{32}$')
        created = datetime.fromisoformat(result['created_at'])
        self.assertIsNotNone(created.utcoffset())
        self.assertEqual(created.strftime('%Y%m%d-%H%M%S-%f'), history_id[:22])
        metadata = {key: value for key, value in result.items() if key != 'image_base64'}
        history = ROOT / 'output/history'
        self.assertEqual(json.loads((history / f'{history_id}.json').read_text(encoding='utf-8')),
                         metadata)
        response = session.get(URL + f'/history/{history_id}/result.json', timeout=10)
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertEqual(response.json(), metadata)
        self.assertNotIn('image_base64', response.json())
        expected_thumbnail = image.convert('RGB')
        expected_thumbnail.thumbnail((160, 100), Image.Resampling.LANCZOS)
        for key, resource in (('source_url', 'source.png'), ('image_url', 'marked.png'),
                              ('thumbnail_url', 'thumbnail.png')):
            with self.subTest(resource=resource):
                self.assertEqual(result[key], f'/history/{history_id}/{resource}')
                response = session.get(URL + result[key], timeout=10)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Content-Type'], 'image/png')
                self.assertEqual(response.content, (history / f'{history_id}-{resource}').read_bytes())
                with Image.open(io.BytesIO(response.content)) as saved:
                    self.assertEqual(saved.format, 'PNG')
                    if resource == 'thumbnail.png':
                        self.assertEqual(saved.size, expected_thumbnail.size)
                        self.assertLessEqual(saved.width, 160)
                        self.assertLessEqual(saved.height, 100)
                    else:
                        self.assertEqual(saved.size, image.size)
                    if resource == 'source.png':
                        self.assertEqual(saved.mode, 'RGB')
                        self.assertEqual(saved.tobytes(), image.convert('RGB').tobytes())
                    elif resource == 'marked.png':
                        self.assertEqual(response.content, base64.b64decode(result['image_base64']))
        response = session.get(URL + '/history/', timeout=10)
        self.assertEqual(response.status_code, 200, response.text[:500])
        listing = response.json()
        ids = [record['history_id'] for record in listing['records']]
        self.assertEqual(ids, sorted(set(ids), reverse=True))
        self.assertEqual(listing['latest_id'], ids[0] if ids else None)
        summary = next(record for record in listing['records'] if record['history_id'] == history_id)
        expected_summary = {key: result[key] for key in (
            'history_id', 'created_at', 'width', 'height',
            'source_url', 'image_url', 'thumbnail_url',
        )}
        expected_summary['element_count'] = len(result['elements'])
        self.assertEqual(summary, expected_summary)
        return result

    def test_image_labels_start_at_one(self):
        import sys
        from unittest.mock import patch

        import numpy as np
        import torch

        sys.path.insert(0, str(ROOT / 'third_party/omniparser'))
        from util import utils

        image = np.full((200, 400, 3), 255, dtype=np.uint8)
        boxes = torch.tensor([[0.25, 0.5, 0.2, 0.2], [0.75, 0.5, 0.2, 0.2]])
        with patch.object(utils.BoxAnnotator, 'annotate', return_value=image) as draw:
            _, coordinates = utils.annotate(image, boxes, None, [1, 2], text_scale=0.45)
        self.assertEqual(draw.call_args.kwargs['labels'], ['1', '2'])
        self.assertEqual(list(coordinates), ['1', '2'])

    def test_blank(self):
        result = self.parse(Image.new('RGB', (640, 480), 'white'))
        self.assertEqual(result['elements'], [])
        self.assertEqual(result['parameters'], {
            'box_threshold': 0.05, 'iou_threshold': 0.7, 'imgsz': 1280,
            'text_threshold': 0.7, 'width_ths': 1.0, 'mag_ratio': 1.0, 'icon_caption': False,
        })

    def test_custom_parameters(self):
        image = Image.new('RGB', (800, 400), 'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 32)
        draw.text((40, 40), '截图自动编号 Save Settings', font=font, fill='black')
        parameters = {'box_threshold': 0.2, 'iou_threshold': 0.5, 'imgsz': 640,
                      'text_threshold': 0.6, 'width_ths': 1.5, 'mag_ratio': 1.5}
        result = self.parse(image, parameters)
        self.assertEqual(result['parameters'], parameters | {'icon_caption': False})
        self.assertTrue(any('截图' in (element['content'] or '')
                            for element in result['elements']))

    def test_invalid_parameters(self):
        encoded = encode(Image.new('RGB', (64, 64), 'white'))
        for parameters in (None, [], {'unknown': 1}, {'box_threshold': 0},
                           {'iou_threshold': 1.1}, {'imgsz': 641}, {'imgsz': 4096},
                           {'text_threshold': '0.7'}, {'width_ths': True},
                           {'width_ths': -1}, {'mag_ratio': 4},
                           {'icon_caption': 1}, {'icon_caption': 'true'},
                           {'icon_caption': None}):
            with self.subTest(parameters=parameters):
                response = session.post(URL + '/parse/',
                                        json={'image_base64': encoded, 'parameters': parameters},
                                        timeout=10)
                self.assertEqual(response.status_code, 400, response.text)

    def test_partial_parameters(self):
        result = self.parse(Image.new('RGB', (64, 64), 'white'), {'imgsz': 640})
        self.assertEqual(result['parameters']['imgsz'], 640)
        self.assertEqual(result['parameters']['width_ths'], 1.0)

    def test_chinese_and_english(self):
        image = Image.new('RGB', (800, 400), 'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 32)
        draw.text((40, 40), '截图自动编号', font=font, fill='black')
        draw.text((40, 120), 'Save Settings', font=font, fill='black')
        result = self.parse(image)
        text = ' '.join(element['content'] or '' for element in result['elements'])
        self.assertIn('截图', text)
        self.assertIn('save', text.lower())
        print('中文/英文 OCR：', text)
        image.save(ROOT / 'output/test-input.png')

    def test_mixed_language_line_not_split(self):
        image = Image.new('RGB', (1000, 240), 'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
        draw.text((40, 100), 'OmniParser 是一款屏幕解析工具，用于将通用 GUI 屏幕转换为结构化元素。',
                  font=font, fill='black')
        result = self.parse(image)
        lines = [element for element in result['elements']
                 if element['content'] and 'omniparser' in element['content'].lower()]
        self.assertEqual(len(lines), 1)
        self.assertIn('GUI', lines[0]['content'])
        self.assertGreater(lines[0]['bbox'][2] * image.width, 450)

    def test_icons_without_text(self):
        image = Image.new('RGB', (320, 240), 'white')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((60, 60, 120, 120), radius=8, fill='#eeeeee', outline='black', width=2)
        draw.line((75, 75, 105, 105), fill='black', width=4)
        draw.line((75, 105, 105, 75), fill='black', width=4)
        self.parse(image)

    def test_icon_caption(self):
        image = Image.new('RGB', (320, 240), 'white')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((60, 60, 120, 120), radius=8, fill='#eeeeee', outline='black', width=2)
        draw.line((75, 75, 105, 105), fill='black', width=4)
        draw.line((75, 105, 105, 75), fill='black', width=4)
        disabled = self.parse(image)
        icons = [element for element in disabled['elements']
                 if element['type'] == 'icon' and element['content'] is None]
        self.assertTrue(icons)
        enabled = self.parse(image, {'icon_caption': True})
        self.assertTrue(enabled['parameters']['icon_caption'])
        self.assertEqual([element['bbox'] for element in enabled['elements']],
                         [element['bbox'] for element in disabled['elements']])
        captions = [element for element in enabled['elements']
                    if element.get('source') == 'box_yolo_content_caption']
        self.assertEqual(len(captions), len(icons))
        self.assertTrue(all(element['content'].strip() for element in captions))
        repeated = self.parse(image, {'icon_caption': True})
        self.assertEqual([element['content'] for element in repeated['elements']],
                         [element['content'] for element in enabled['elements']])
        restored = self.parse(image, {'icon_caption': False})
        self.assertEqual(restored['elements'], disabled['elements'])
        print('图标描述：', [element['content'] for element in captions])

    def test_caption_empty_and_text_only(self):
        import sys
        from unittest.mock import patch

        import numpy as np
        import torch

        sys.path.insert(0, str(ROOT / 'third_party/omniparser'))
        from util import utils

        for texts, boxes in (([], []), (['Save'], [[10, 10, 60, 40]])):
            with self.subTest(texts=texts), patch.object(utils, 'predict_yolo', return_value=(
                    torch.empty((0, 4)), torch.empty(0), [])), patch.object(
                    utils, 'get_parsed_content_icon') as caption:
                _, _, elements = utils.get_som_labeled_img(
                    Image.new('RGB', (100, 100), 'white'), ocr_bbox=boxes,
                    ocr_text=texts, use_local_semantics=True)
                caption.assert_not_called()
                self.assertEqual([element['content'] for element in elements], texts)
        result = self.parse(Image.new('RGB', (640, 480), 'white'), {'icon_caption': True})
        self.assertEqual(result['elements'], [])

    def test_caption_crop_alignment(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock

        import numpy as np
        import torch

        sys.path.insert(0, str(ROOT / 'third_party/omniparser'))
        from util import utils

        model = Mock()
        model.device = torch.device('cpu')
        model.config = SimpleNamespace(model_type='florence2', name_or_path='local/model')
        processor = Mock()
        processor.return_value.to.return_value = {'input_ids': torch.ones((3, 1)),
                                                 'pixel_values': torch.ones((3, 3, 64, 64))}
        processor.batch_decode.return_value = ['first', 'second', 'third']
        boxes = torch.tensor([[0, 0, 0.001, 0.001], [-0.1, 0, 0.2, 0.2], [0.9, 0.9, 1.1, 1.1]])
        captions = utils.get_parsed_content_icon(
            boxes, 0, np.zeros((20, 20, 3), dtype=np.uint8),
            {'model': model, 'processor': processor}, batch_size=16)
        self.assertEqual(captions, ['first', 'second', 'third'])
        self.assertEqual(len(processor.call_args.kwargs['images']), 3)
        self.assertEqual(processor.call_args.kwargs['text'], ['<CAPTION>'] * 3)

    def test_history_same_size_does_not_overwrite(self):
        first = self.parse(Image.new('RGBA', (64, 64), (255, 255, 255, 128)), {'imgsz': 640})
        history = ROOT / 'output/history'
        first_files = {path: path.read_bytes()
                       for path in history.glob(first['history_id'] + '*')}
        self.assertEqual(len(first_files), 4)
        second = self.parse(Image.new('RGB', (64, 64), 'black'), {'imgsz': 640})
        self.assertNotEqual(first['history_id'], second['history_id'])
        for path, contents in first_files.items():
            self.assertEqual(path.read_bytes(), contents)
        response = session.get(URL + f"/history/{first['history_id']}/result.json", timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {key: value for key, value in first.items()
                                           if key != 'image_base64'})
        listing = session.get(URL + '/history/', timeout=10).json()
        ids = [record['history_id'] for record in listing['records']]
        self.assertLess(ids.index(second['history_id']), ids.index(first['history_id']))
        self.assertEqual(listing['latest_id'], second['history_id'])
        self.assertEqual((ROOT / 'output/latest.png').read_bytes(),
                         base64.b64decode(second['image_base64']))
        self.assertEqual(json.loads((ROOT / 'output/latest.json').read_text(encoding='utf-8')),
                         {key: value for key, value in second.items() if key != 'image_base64'})

    def test_invalid_history_routes(self):
        missing_id = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid4().hex
        paths = [f'/history/{missing_id}/{resource}' for resource in (
            'result.json', 'source.png', 'marked.png', 'thumbnail.png',
        )]
        paths += [
            '/history', '/history/invalid/result.json',
            f'/history/{missing_id.upper()}/source.png',
            f'/history/{missing_id}/latest.json', f'/history/{missing_id}/source.jpg',
            f'/history/{missing_id}/source.png/extra',
            f'/history/{missing_id}/source.png?file=latest.png',
            '/history/../latest.json', '/history/%2e%2e%2flatest.json',
            f'/history/{missing_id}/%2e%2e%2f%2e%2e%2flatest.png',
            f'/history/{missing_id}/..%5clatest.json',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = session.get(URL + path, timeout=10)
                self.assertEqual(response.status_code, 404, response.text[:500])
                self.assertIn('application/json', response.headers['Content-Type'])
                self.assertTrue(any('\u4e00' <= char <= '\u9fff'
                                    for char in response.json()['error']))

    def test_history_host_validation(self):
        history_id = datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid4().hex
        for path in ('/history/', *(f'/history/{history_id}/{resource}' for resource in (
                'result.json', 'source.png', 'marked.png', 'thumbnail.png'))):
            with self.subTest(path=path):
                response = session.get(URL + path, headers={'Host': 'example.com'}, timeout=10)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {'error': '仅允许本机访问。'})
        response = session.get(URL + '/history/', headers={'Host': 'localhost:17897'}, timeout=10)
        self.assertEqual(response.status_code, 200)

    def test_invalid_input(self):
        for payload in ({}, {'image_base64': 'not-an-image'}, [], {'image_base64': 3}):
            response = session.post(URL + '/parse/', json=payload, timeout=10)
            self.assertEqual(response.status_code, 400)

    def test_external_origin_blocked(self):
        response = session.post(URL + '/parse/', json={}, headers={'Origin': 'https://example.com'}, timeout=10)
        self.assertEqual(response.status_code, 403)
        response = session.get(URL + '/probe/', headers={'Host': 'example.com'}, timeout=10)
        self.assertEqual(response.status_code, 403)

    def test_web_ui(self):
        response = session.get(URL + '/', timeout=10)
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['Content-Type'])
        self.assertEqual(response.content, (ROOT / 'web/index.html').read_bytes())
        self.assertIn('OmniParser V2 Web UI', response.text)

    @unittest.skipUnless((ROOT / 'tests/fixtures/reference.png').is_file(), '本地参考截图不存在。')
    def test_reference(self):
        with Image.open(ROOT / 'tests/fixtures/reference.png') as image:
            result = self.parse(image.convert('RGB'))
        self.assertGreater(len(result['elements']), 10)
        (ROOT / 'output/reference-annotated.png').write_bytes(base64.b64decode(result['image_base64']))
        print(f"参考截图：{len(result['elements'])} 个元素，{result['seconds']} 秒")


if __name__ == '__main__':
    unittest.main(verbosity=2)
