# OmniParser V2 Web UI

<a href="README.md"><kbd>简体中文</kbd></a> · <a href="README.en.md"><kbd>English</kbd></a>

基于 Microsoft OmniParser 的本地截图解析 Web UI，面向 Windows 和 NVIDIA GPU。前端为原生 HTML/CSS/JavaScript，后端使用 Python 标准库 HTTP 服务，不需要 Node.js 或前端构建工具。

当前提供图标检测、中英文 OCR、可选的图标语义描述、可选的图标分类描述、从 1 开始的元素编号、参数调整、图片缩放、图片与 JSON 导出，以及历史记录恢复。Windows 托盘入口保留全屏、框选和剪贴板处理功能。

支持可选的 OmniParser V2 Florence-2 图标语义描述，默认关闭；另有同模型的封闭集合图标分类描述，默认关闭，两者不能同时开启。检测器使用上游新增的 YOLOv9-E（`icon_detect_v3`），并非直接复刻官方完整推理配置。

## 环境与安装

已验证环境：Windows、Python 3.12.10、PyTorch 2.8.0 + CUDA 12.8、RTX 5070 Ti。需要支持 CUDA 12.8 的 NVIDIA 驱动；目前不支持 CPU 启动。

在项目根目录执行 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\download_models.py
```

已有 `.venv` 和模型时无需重新安装。下载脚本固定检测模型的 Hugging Face 版本，并校验 EasyOCR 模型。源码已包含运行所需的上游文件，无需另外克隆 OmniParser。

## 手动下载模型

也可以用浏览器或下载工具下载下列文件，手动创建对应目录并放入项目根目录下的 `models/`，无需运行下载脚本。链接固定到与项目一致的版本，请保留文件名，不要用官方旧版 `icon_detect/model.pt` 替代这里的 `icon_detect_v3/model.pt`。Python 依赖仍需按上面的步骤安装。

### 必需：图标检测和中英文 OCR

| 模型 | 下载地址 | 放置位置（相对项目根目录） |
| --- | --- | --- |
| YOLOv9-E 图标检测 | [model.pt](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/d10c4687d4af8245d67780ae59900f09660aad3a/icon_detect_v3/model.pt?download=true) | `models/icon_detect_v3/model.pt` |
| EasyOCR 文字检测 | [craft_mlt_25k.zip](https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip) | 解压其中的 `craft_mlt_25k.pth` 到 `models/ocr/` |
| EasyOCR 中英文识别 | [zh_sim_g2.zip](https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/zh_sim_g2.zip) | 解压其中的 `zh_sim_g2.pth` 到 `models/ocr/` |

OCR 的 ZIP 不能直接作为模型使用，必须解压；`.pth` 文件不要再套一层子目录。只使用检测和 OCR 时，准备好以上 3 个文件即可启动。

### 可选：Florence-2 图标语义描述

以下 **11 个文件全部放入 `models/icon_caption/`**，不要再嵌套 `icon_caption/` 或模型仓库名目录。只下载 `model.safetensors` 不足以运行。

| 来源 | 文件下载地址 |
| --- | --- |
| OmniParser V2 微调权重与配置 | [model.safetensors](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/model.safetensors?download=true) · [config.json](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/config.json?download=true) · [generation_config.json](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/generation_config.json?download=true) · [LICENSE](https://huggingface.co/microsoft/OmniParser-v2.0/resolve/f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4/icon_caption/LICENSE?download=true) |
| Florence-2-base 处理器与分词器 | [preprocessor_config.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/preprocessor_config.json?download=true) · [processing_florence2.py](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/processing_florence2.py?download=true) · [tokenizer.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/tokenizer.json?download=true) · [tokenizer_config.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/tokenizer_config.json?download=true) · [vocab.json](https://huggingface.co/microsoft/Florence-2-base/resolve/5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac/vocab.json?download=true) |
| Florence-2-base-ft 架构代码 | [configuration_florence2.py](https://huggingface.co/microsoft/Florence-2-base-ft/resolve/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e/configuration_florence2.py?download=true) · [modeling_florence2.py](https://huggingface.co/microsoft/Florence-2-base-ft/resolve/f6c1a25888ffc1d945ee8a1a77ac833c7303d46e/modeling_florence2.py?download=true) |

**手动下载后还需修改 `models/icon_caption/config.json`**：仅将顶层 `auto_map` 替换为以下内容，保留其他配置不变。官方配置引用另一个在线仓库的代码，改成本地引用后才能完全离线加载；自动下载脚本已经包含这一步。

```json
"auto_map": {
  "AutoConfig": "configuration_florence2.Florence2Config",
  "AutoModelForCausalLM": "modeling_florence2.Florence2ForConditionalGeneration"
}
```

无需下载 Florence-2-base 或 Florence-2-base-ft 的原始权重，也不需要 `pytorch_model.bin`；描述权重必须使用表中的 OmniParser V2 微调版本。下载 Python 文件时保存原始代码，不要保存成网页 HTML。

完成后的目录如下（不启用语义描述时可省略整个 `icon_caption/`）：

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

Hugging Face 下载链接可将域名 `huggingface.co` 替换为 `hf-mirror.com` 尝试镜像，保留后面的版本和文件路径；镜像可用性取决于网络及同步状态。文件准备好后直接启动服务，无需再次运行下载脚本。替换模型或配置前先停止服务，放置完成后重新启动；模型文件不会进入 Git。

## 图标语义描述（可选）

额外下载描述权重、处理器和固定版本的模型代码：

```powershell
.\.venv\Scripts\python.exe scripts\download_models.py --caption
```

网络需要代理时，可先在当前 PowerShell 窗口设置：

```powershell
$env:HTTPS_PROXY = 'http://127.0.0.1:7897'
$env:HTTP_PROXY = 'http://127.0.0.1:7897'
```

下载脚本支持通过 `$env:HF_ENDPOINT = 'https://hf-mirror.com'` 指定镜像，但本次验证中镜像缺少下载库要求的版本元数据，未能完成语义权重下载；推荐优先使用官方源配合代理。大文件下载可能超时或连接中断，重新运行相同命令可从已有缓存续传，不必删除缓存。描述权重约 1.08 GB，处理器和架构代码另占少量空间；下载完成后运行不需要联网。

网页“识别参数”中的“图标语义描述”默认未勾选。开启后，仅对没有 OCR 文字的图标生成描述，写入元素的 `content`，来源标记为 `box_yolo_content_caption`；原有 OCR 文字不被替换。描述保留模型原始输出（通常为英文），不额外翻译，也可能误判图标用途，仅供参考。

首次遇到待描述图标时才加载模型；没有图标或关闭开关时不加载。模型按 16 个图标一批推理，后续请求复用。首次加载和开启推理会增加耗时；关闭开关停止描述，但不会卸载已加载模型，退出服务才释放显存。开关状态随历史记录与 JSON 一同保存，旧历史记录按关闭处理。托盘截图仍默认关闭语义描述。

模型目录包含固定版本的 Florence-2 Python 架构代码，加载时使用 `trust_remote_code=True`，但只读取已下载的本地文件；请勿用不可信来源替换模型目录。

## 图标分类描述（可选）

复用同一份 Florence-2 权重，但不再让模型自由写句子，而是从固定的 24 个类别里选一个，输出类别名和候选集内的相对分数。适合需要直接判断按钮用途、把结果交给代码消费的场合。

类别固定为：`search`、`settings`、`close`、`file`、`add`、`delete`、`menu`、`edit`、`share`、`download`、`user`、`star`、`lock`、`mail`、`camera`、`minus`、`arrow`、`check`、`warning`、`image`、`play`、`pause`、`home`、`back`。

开启后同样只处理没有 OCR 文字的图标，写入 `content`，来源标记为 `box_yolo_content_label`，并额外写入 `confidence`：

```json
{"id": 61, "type": "icon", "content": "settings", "confidence": 0.204,
 "source": "box_yolo_content_label", "bbox": [0.814, 0.073, 0.833, 0.088]}
```

实现方式是只解码到首个内容 token，读该位置的输出分布，因此比自由描述（最多 20 个 token）快，但首次加载模型的耗时相同。类别表在 `server.py` 的 `ICON_LABELS` 中定义，**每个类别必须是 Florence-2 词表里的单个 token**，否则请求会直接报错而不是静默降级；例如 `trash` 会被切成两个 token，不能加入。

**`confidence` 不是准确率。** 它只是该类别在 24 个候选内的 softmax 占比，换一套类别表数值就会变，也没有做过温度标定。它可用于同一类别间的相对排序，不能当作“这个判断有 X% 可能正确”来设阈值。

已实测的限制：

- 语义型图标（关闭、设置、搜索、复选框、用户头像）通常能对上，纯图形符号（加号、减号、箭头、展开收起）容易判错——图标缩小到 64×64 后笔画信息损失明显，而 Florence-2-base 本身对抽象符号没有好的表示。
- 与“图标语义描述”互斥，同时开启会被拒绝；网页端会自动取消另一个开关。
- 类别数越少，候选内归一化的失真越小；如需精简类别表，可只保留下游真正用到的十几个。

若要把 `confidence` 当作真实置信度使用，需要另做标定：用几百个自己截的真实图标做标注集，拟合温度参数使其与经验正确率对齐，再按分位数定阈值。这项标定尚未实现。

### 本机实测性能

在 RTX 5070 Ti 16GB、Python 3.12.10、PyTorch 2.8.0 + CUDA 12.8 上验证：

| 场景 | 耗时 |
| --- | --- |
| 单图标首次加载模型并描述 | 9.27 秒 |
| 同一图标后续描述 | 0.49 秒 |
| 1234 × 1234 参考截图，关闭描述 | 2.01 秒 |
| 同一截图，为 8 个图标生成描述（模型已加载） | 3.04–3.25 秒 |
| 同一截图，为 8 个图标做分类描述（模型已加载） | 2.96 秒 |

FP16 语义模型权重单独占用约 453 MiB 显存，不包含检测模型、OCR、推理临时内存或 PyTorch 缓存。以上为单次本机测试结果，不是性能保证；实际耗时和显存需求随截图大小、图标数量和 GPU 环境变化。极小图标、误检区域或缺少上下文的图标描述尤其容易不准确。分类描述比自由描述省掉大部分解码步骤，但单张截图的耗时差距主要被检测和 OCR 占据，因此总时长差别有限。

## 启动与使用

双击 `Start.cmd`，或在 PowerShell 执行：

```powershell
.\Start.cmd
```

启动后自动打开 `http://127.0.0.1:17897`，并在托盘注册：

- `Ctrl+Alt+F8`：全屏截图并编号。
- `Ctrl+Alt+F9`：框选截图并编号。
- 托盘菜单：处理剪贴板图片、打开页面和退出。

从托盘退出会关闭本次入口启动的识别服务，不会关闭原先已在运行的服务。

只使用 Web UI、不需要托盘和热键时：

```powershell
.\.venv\Scripts\python.exe -u server.py
```

然后自行打开本地地址；按 `Ctrl+C` 停止。直接运行时日志输出到终端，托盘启动时日志写入 `logs/`。

在网页中选择、拖入或粘贴图片，点击“自动框选编号”。结果坐标为归一化的 `[x1, y1, x2, y2]`，范围为 0–1。历史记录保存在 `output/history/`，最新结果另存为 `output/latest.png` 和 `output/latest.json`。

## 项目结构

```text
server.py                    Python HTTP 服务与推理流程
Start.cmd / Start.ps1        Windows 托盘启动入口
requirements.txt            Python 依赖，指定 CUDA 12.8 版 PyTorch
web/index.html              Web UI
scripts/                    模型下载、截图与剪贴板脚本
tests/                      接口与 Windows 进程生命周期测试
third_party/omniparser/      上游运行源码、许可证与来源说明
models/                     本地模型（不进入 Git）
output/                     识别结果与历史记录（不进入 Git）
logs/                       运行日志（不进入 Git）
local/archive/              整理前的完整上游仓库和旧页面（不进入 Git）
```

`.venv/`、工具缓存、模型、截图历史、日志和本地归档均由 `.gitignore` 排除。`local/archive/OmniParser/` 保留原来的 `.git` 和本地修改，但新项目运行不依赖它。

## 测试

完整测试包含真实图标语义和分类推理，需先安装 `requirements.txt` 中的依赖，并运行 `scripts/download_models.py --caption` 或按手动下载说明准备全部模型及本地配置。启动识别服务后，在另一个 PowerShell 窗口执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File tests\test_startup.ps1
```

已验证 21 项 Python 测试全部通过，覆盖语义描述开关、分类描述、裁剪与描述对应、空图及纯文字、历史保存、参数校验和本机访问限制；模型和处理器已验证可以完全离线加载。网页中的描述显示、历史恢复及恢复默认也已实际验证。

接口测试需要 GPU，会生成本地历史记录；中文测试使用 Windows 微软雅黑字体。原参考截图保留在 `tests/fixtures/reference.png`，为避免把个人截图发布到仓库，该文件不进入 Git；缺少该图时参考截图测试跳过，其余测试使用现场生成的图片。

## 本地访问与数据

服务仅监听 `127.0.0.1:17897`，并校验 Host 和请求来源。当前没有用户登录或远程部署能力，不应直接暴露到公网。完成模型下载后，识别流程在本机运行。原图、编号图和识别文字会落盘，请勿将 `output/` 加入仓库。

## 上游与许可

本项目不是 Microsoft 官方 Web UI。上游源码来源、固定版本、本地修改和许可证见 [third_party/omniparser/NOTICE.md](third_party/omniparser/NOTICE.md)。模型和第三方依赖各自遵循其许可；本项目自有代码尚未指定开源许可证。
