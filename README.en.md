# OmniParser V2 Web UI

<a href="README.md"><kbd>简体中文</kbd></a> · <a href="README.en.md"><kbd>English</kbd></a>

A local screenshot parsing Web UI based on Microsoft OmniParser, designed for Windows and NVIDIA GPUs. The frontend uses plain HTML/CSS/JavaScript, and the backend uses Python's standard-library HTTP server. No Node.js or frontend build tools are required.

Current features include icon detection, Chinese and English OCR, optional icon captioning, optional closed-set icon classification, element numbering starting at 1, adjustable inference parameters, image zoom, image and JSON export, and history restoration. The Windows system tray launcher also provides full-screen capture, region capture, and clipboard image processing.

Optional OmniParser V2 Florence-2 icon captioning is supported and disabled by default; a closed-set icon classification mode using the same model is also available, disabled by default, and the two cannot be enabled together. The detector uses the upstream YOLOv9-E implementation (`icon_detect_v3`), rather than directly reproducing the complete official inference configuration.

## Environment and Installation

Verified environment: Windows, Python 3.12.10, PyTorch 2.8.0 with CUDA 12.8, and an RTX 5070 Ti. An NVIDIA driver supporting CUDA 12.8 is required. CPU startup is not currently supported.

Run the following in PowerShell from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\download_models.py
```

If `.venv` and the models already exist, reinstalling is unnecessary. The download script pins the Hugging Face revision of the detection model and verifies the EasyOCR models. The required upstream source files are included, so there is no need to clone OmniParser separately.

## Manual Model Downloads

You can also download the files below using a browser or download manager, create the matching directories, and place them under `models/` in the project root without running the download script. Links are pinned to the revisions used by this project. Keep the original filenames; do not replace `icon_detect_v3/model.pt` with the older official `icon_detect/model.pt`. Python dependencies must still be installed as described above.

### Required: Icon Detection and Chinese/English OCR

| Model | Download | Destination relative to the project root |
| --- | --- | --- |
| YOLOv9-E icon detector | [model.pt](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/d10c4687d4af8245d67780ae59900f09660aad3a/icon_detect_v3/model.pt?download=true) | `models/icon_detect_v3/model.pt` |
| EasyOCR text detector | [craft_mlt_25k.zip](https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip) | Extract `craft_mlt_25k.pth` into `models/ocr/` |
| EasyOCR Chinese/English recognizer | [zh_sim_g2.zip](https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/zh_sim_g2.zip) | Extract `zh_sim_g2.pth` into `models/ocr/` |

The OCR ZIP archives must be extracted; they cannot be used directly. Do not place the `.pth` files inside an extra subdirectory. These three files are sufficient to launch detection and OCR without captioning.

### Optional: Florence-2 Icon Captioning

Place **all 11 files below directly in `models/icon_caption/`**, without an extra `icon_caption/` or repository-name subdirectory. Downloading only `model.safetensors` is not sufficient.

| Source | File downloads |
| --- | --- |
| OmniParser V2 fine-tuned weights and configuration | [model.safetensors](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/model.safetensors?download=true) · [config.json](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/config.json?download=true) · [generation_config.json](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/generation_config.json?download=true) · [LICENSE](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/LICENSE?download=true) |
| Florence-2-base processor and tokenizer | [preprocessor_config.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/preprocessor_config.json?download=true) · [processing_florence2.py](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/processing_florence2.py?download=true) · [tokenizer.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/tokenizer.json?download=true) · [tokenizer_config.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/tokenizer_config.json?download=true) · [vocab.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/vocab.json?download=true) |
| Florence-2-base-ft architecture code | [configuration_florence2.py](https://huggingface.co/microsoft/Florence-2-base-ft/resolve/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e/configuration_florence2.py?download=true) · [modeling_florence2.py](https://huggingface.co/microsoft/Florence-2-base-ft/resolve/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e/modeling_florence2.py?download=true) |

**After downloading manually, edit `models/icon_caption/config.json`**: replace only its top-level `auto_map` with the following, leaving all other configuration unchanged. The official configuration references code in another online repository; local references are required for fully offline loading. The automatic download script already performs this step.

```json
"auto_map": {
  "AutoConfig": "configuration_florence2.Florence2Config",
  "AutoModelForCausalLM": "modeling_florence2.Florence2ForConditionalGeneration"
}
```

You do not need the original Florence-2-base or Florence-2-base-ft weights or `pytorch_model.bin`. Use the OmniParser V2 fine-tuned caption weights linked above. Save Python files as raw source code, not as HTML pages.

The resulting layout should be as follows. The entire `icon_caption/` directory is optional when captioning is disabled:

```text
models/
├── icon_detect_v3/
│   └── model.pt
├── ocr/
│   ├── craft_mlt_25k.pth
│   └── zh_sim_g2.pth
└── icon_caption/
    ├── model.safetensors
    ├── config.json
    ├── generation_config.json
    ├── LICENSE
    ├── preprocessor_config.json
    ├── processing_florence2.py
    ├── tokenizer.json
    ├── tokenizer_config.json
    ├── vocab.json
    ├── configuration_florence2.py
    └── modeling_florence2.py
```

To try a mirror, replace `huggingface.co` with `hf-mirror.com` in the download links while retaining the revision and file path. Mirror availability depends on your network and its synchronization status. Once the files are ready, launch the server directly without rerunning the download script. Stop the server before replacing models or configuration, then restart it after placing the files. Model files remain excluded from Git.

## Optional Icon Captioning

Download the caption weights, processor, and pinned model code:

```powershell
.\.venv\Scripts\python.exe scripts\download_models.py --caption
```

If your network requires a proxy, first set it in the current PowerShell window:

```powershell
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
```

The download script supports selecting a mirror with `$env:HF_ENDPOINT = 'https://hf-mirror.com'`. However, during this verification the mirror lacked revision metadata required by the download library, so it could not complete the caption weight download. Prefer the official source with a proxy. Large downloads may time out or disconnect; rerun the same command to resume from the existing cache without deleting it. Caption weights are approximately 1.08 GB, with a small amount of additional space needed for the processor and architecture code. Runtime inference requires no network access after downloading.

The “图标语义描述” (Icon captioning) checkbox under inference parameters is unchecked by default. When enabled, only icons without OCR text receive generated descriptions in their `content` field, with `source` set to `box_yolo_content_caption`. Existing OCR text is preserved. Descriptions retain the model's original output, usually English, without translation. They may misinterpret an icon's purpose and should be treated as suggestions.

The model loads only when an enabled request contains icons requiring captions. Disabled requests and images without such icons do not load it. Inference uses batches of 16 icons, and subsequent requests reuse the loaded model. Initial loading and caption inference increase latency. Turning the checkbox off stops captioning but does not unload the model; exiting the server releases GPU memory. The option is saved with history and JSON; older records default to disabled. System tray captures still default to captioning disabled.

The model directory contains pinned Florence-2 Python architecture code. Loading uses `trust_remote_code=True` but reads downloaded local files only. Do not replace these files with material from untrusted sources.

## Closed-Set Icon Classification (Optional)

Reuses the same Florence-2 weights, but instead of writing a free-form sentence the model must pick one of 24 fixed labels, returning the label name and a score relative to that candidate set. This suits cases where downstream code needs to decide what a button does.

The labels are fixed: `search`, `settings`, `close`, `file`, `add`, `delete`, `menu`, `edit`, `share`, `download`, `user`, `star`, `lock`, `mail`, `camera`, `minus`, `arrow`, `check`, `warning`, `image`, `play`, `pause`, `home`, `back`.

When enabled, only icons without OCR text are classified. The label goes into `content`, `source` becomes `box_yolo_content_label`, and an extra `confidence` field is written:

```json
{"id": 61, "type": "icon", "content": "settings", "confidence": 0.204,
 "source": "box_yolo_content_label", "bbox": [0.814, 0.073, 0.833, 0.088]}
```

It decodes only up to the first content token and reads the distribution there, so it is faster than free-form captioning (up to 20 tokens), while the initial model load costs the same. The label list is `ICON_LABELS` in `server.py`. **Every label must be a single token in the Florence-2 vocabulary**; otherwise the request fails instead of silently degrading. For example, `trash` splits into two tokens and cannot be added.

**`confidence` is not an accuracy figure.** It is only the softmax share among the 24 candidates; changing the label list changes the number, and no temperature calibration has been done. It is usable for relative ordering, not as "this decision is X% likely correct" for thresholding.

Measured limitations:

- Semantic icons (close, settings, search, checkbox, user avatar) usually match; purely graphical symbols (plus, minus, arrows, expand/collapse) are often wrong — downscaling icons to 64×64 loses stroke detail, and Florence-2-base has no good representation for abstract symbols.
- Mutually exclusive with icon captioning; enabling both is rejected, and the web UI clears the other checkbox automatically.
- Fewer labels means less distortion from renormalising inside the candidate set; trim the list to the dozen or so labels downstream actually uses if needed.

Using `confidence` as a real probability requires calibration: build a labelled set of a few hundred of your own icon crops, fit a temperature parameter so predictions match empirical accuracy, then set thresholds by quantile. That calibration is not implemented.

### Local Performance Measurements

Verified on an RTX 5070 Ti 16GB with Python 3.12.10 and PyTorch 2.8.0 + CUDA 12.8:

| Scenario | Time |
| --- | --- |
| First model load and caption for one icon | 9.27 seconds |
| Subsequent caption for the same icon | 0.49 seconds |
| 1234 × 1234 reference screenshot, captioning disabled | 2.01 seconds |
| Same screenshot, captioning 8 icons with the model already loaded | 3.04–3.25 seconds |
| Same screenshot, classifying 8 icons with the model already loaded | 2.96 seconds |

FP16 caption model weights alone use approximately 453 MiB of GPU memory, excluding the detector, OCR, temporary inference memory, and PyTorch caches. These are individual local measurements, not performance guarantees. Latency and memory requirements vary with image size, icon count, and GPU environment. Captions for very small icons, false detections, or icons lacking context are particularly prone to inaccuracies. Classification skips most decoding steps, but on a single screenshot detection and OCR dominate the total, so end-to-end times differ little.

## Launch and Usage

Double-click `Start.cmd`, or run it in PowerShell:

```powershell
.\Start.cmd
```

The launcher automatically opens `http://127.0.0.1:17897` and registers these system tray shortcuts:

- `Ctrl+Alt+F8`: Capture the full screen and label detected elements.
- `Ctrl+Alt+F9`: Capture a selected region and label detected elements.
- System tray menu: Process a clipboard image, open the page, or exit.

Exiting from the system tray stops the inference server started by that launcher instance. It does not stop a server that was already running.

To use only the Web UI without the system tray or hotkeys:

```powershell
.\.venv\Scripts\python.exe -u server.py
```

Open the local URL manually and press `Ctrl+C` to stop the server. When run directly, logs appear in the terminal; when started through the system tray launcher, logs are written to `logs/`.

Select, drag and drop, or paste an image into the page, then click “自动框选编号” (Automatically detect and number elements). Bounding boxes use normalized `[x1, y1, x2, y2]` coordinates in the range 0–1. History is saved in `output/history/`, and the latest result is also saved as `output/latest.png` and `output/latest.json`.

## Project Structure

```text
server.py                    Python HTTP server and inference pipeline
Start.cmd / Start.ps1        Windows system tray launcher
requirements.txt            Python dependencies with CUDA 12.8 PyTorch
web/index.html              Web UI
scripts/                    Model download, capture, and clipboard scripts
tests/                      API and Windows process lifecycle tests
third_party/omniparser/      Upstream runtime source, license, and attribution
models/                     Local models (excluded from Git)
output/                     Results and history (excluded from Git)
logs/                       Runtime logs (excluded from Git)
local/archive/              Original upstream repository and old page (excluded from Git)
```

`.venv/`, tool caches, models, screenshot history, logs, and local archives are excluded by `.gitignore`. `local/archive/OmniParser/` retains the original `.git` directory and local changes, but the new project does not depend on it at runtime.

## Tests

The full suite includes real icon caption and classification inference. First install the dependencies in `requirements.txt`, then run `scripts/download_models.py --caption` or prepare all models and local configuration using the manual download instructions. Start the inference server, then run the following in another PowerShell window:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tests\test_startup.ps1
```

All 21 Python tests passed during verification, covering captioning on/off, closed-set classification, crop-to-caption alignment, blank and text-only images, history persistence, parameter validation, and local access restrictions. Fully offline model and processor loading was also verified, along with caption display, history restoration, and resetting defaults in the browser.

API tests require a GPU and generate local history records. Chinese OCR tests use the Microsoft YaHei font on Windows. The original reference screenshot is retained at `tests/fixtures/reference.png` but excluded from Git to avoid publishing a personal screenshot. The reference screenshot test is skipped when that file is missing; the remaining tests use generated images.

## Local Access and Data

The server listens only on `127.0.0.1:17897` and validates the Host header and request origin. There is currently no user authentication or remote deployment support, so the server should not be exposed directly to the internet. After the models have been downloaded, inference runs locally. Original images, labeled images, and recognized text are saved to disk; do not add `output/` to the repository.

## Upstream and Licensing

This is not an official Microsoft Web UI. See [third_party/omniparser/NOTICE.md](third_party/omniparser/NOTICE.md) for the upstream source, pinned revision, local modifications, and license. Models and third-party dependencies are subject to their respective licenses. No open-source license has yet been assigned to this project's own code.
