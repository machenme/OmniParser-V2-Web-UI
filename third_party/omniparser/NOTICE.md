# OmniParser 上游来源与本地修改

运行源码来自 Microsoft 的 [OmniParser](https://github.com/microsoft/OmniParser) 仓库，基准提交为 `354021201345a96178360b28733573e27269f2de`。

本目录保留运行所需的 `util/__init__.py`、`util/utils.py`、`util/box_annotator.py` 和 `util/yolov9.py`。上游 LICENSE 原文保存在本目录的 `LICENSE`，为 CC BY 4.0，并包含免责声明。本项目并非 Microsoft 官方产品，也不表示获得其认可。

相对于上游，`util/utils.py` 保留了以下本地修改：

- 移除未使用的 AzureOpenAI 导入。
- EasyOCR 和 PaddleOCR 改为延迟初始化；EasyOCR 默认支持简体中文和英文。
- 修正无 OCR 时图标元素的返回结构。
- 允许空检测结果，维持边界框张量的二维形状。
- 编号及图像标签从 1 开始，坐标索引与标签一致。
- 图标描述裁剪限制到有效像素区域，不静默跳过裁剪，保持描述与图标一一对应。
- 无待描述图标时跳过语义推理，通过 model_type 识别 Florence-2 本地模型。

当前服务显式指定 `models/icon_detect_v3/model.pt`。检测权重来自 Hugging Face 的 `microsoft/OmniParser-v2.0`，文件为 `icon_detect_v3/model.pt`，固定 revision 为 `d10c4687d4af8245d67780ae59900f09660aad3a`，对应整理前已经下载的模型版本。模型权重不随 Git 分发，其许可应以模型发布方说明为准。

可选语义模型使用 `microsoft/OmniParser-v2.0` 的 `icon_caption/`，revision 为 `f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4`；处理器来自 `microsoft/Florence-2-base` 的 `5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac`；架构代码来自 `microsoft/Florence-2-base-ft` 的 `f6c1a25888ffc1d945ee8a1a77ac833c7303d46e`。下载脚本将配置中的跨仓库代码引用改为本地引用，以便离线加载。语义权重和所需代码均保存在 Git 忽略的 `models/icon_caption/`，该目录保留发布方的 MIT LICENSE。

EasyOCR 权重来自 JaidedAI/EasyOCR 的官方 GitHub Releases，通过 `scripts/download_models.py` 下载并校验；EasyOCR 及其他依赖遵循各自许可。
