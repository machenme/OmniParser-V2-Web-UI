import argparse
import hashlib
import json
import os
import urllib.request
import zipfile
from pathlib import Path

os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='下载 OmniParser V2 Web UI 本地模型。')
parser.add_argument('--caption', action='store_true', help='同时下载可选的图标语义描述模型。')
args = parser.parse_args()
path = hf_hub_download(
    'microsoft/OmniParser-v2.0', 'icon_detect_v3/model.pt',
    revision='d10c4687d4af8245d67780ae59900f09660aad3a', local_dir=ROOT / 'models',
)
print(f'检测模型：{path}', flush=True)

OCR = ROOT / 'models/ocr'
OCR.mkdir(parents=True, exist_ok=True)
models = [
    ('craft_mlt_25k', 'https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip', '2f8227d2def4037cdb3b34389dcf9ec1'),
    ('zh_sim_g2', 'https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/zh_sim_g2.zip', 'b601ce7143293387d3ec4f41a66edc07'),
]
for name, url, checksum in models:
    target = OCR / f'{name}.pth'
    if not target.exists():
        archive = OCR / f'{name}.zip'
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zipped:
            with zipped.open(f'{name}.pth') as source, target.open('wb') as dest:
                import shutil
                shutil.copyfileobj(source, dest)
    actual = hashlib.md5(target.read_bytes()).hexdigest()
    if actual != checksum:
        raise RuntimeError(f'OCR 模型校验失败：{target}')
    print(f'OCR 模型已验证：{target}', flush=True)

if args.caption:
    caption_dir = ROOT / 'models/icon_caption'
    sources = [
        ('microsoft/OmniParser-v2.0', 'f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4',
         ['icon_caption/config.json', 'icon_caption/generation_config.json',
          'icon_caption/model.safetensors', 'icon_caption/LICENSE']),
        ('microsoft/Florence-2-base', '5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac',
         ['preprocessor_config.json', 'processing_florence2.py',
          'tokenizer.json', 'tokenizer_config.json', 'vocab.json']),
        ('microsoft/Florence-2-base-ft', 'f6c1a25888ffc1d945ee8a1a77ac833c7303d46e',
         ['configuration_florence2.py', 'modeling_florence2.py']),
    ]
    for repo, revision, files in sources:
        for filename in files:
            directory = ROOT / 'models' if filename.startswith('icon_caption/') else caption_dir
            downloaded = hf_hub_download(repo, filename, revision=revision, local_dir=directory)
            print(f'语义模型文件：{downloaded}', flush=True)
    config_path = caption_dir / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['auto_map'] = {name: target.split('--')[-1]
                          for name, target in config['auto_map'].items()}
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print('图标语义描述模型已就绪，可离线加载。', flush=True)
