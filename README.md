# AI-Cartoon-Live

**[简体中文](README.md) | [English](README.en.md)**

<img src="assets/whale.png" alt="鲸鱼娘示例角色" width="160">

**在一台带 NVIDIA 显卡的本地电脑上，运行能对话、记忆、做表情和参与直播的二次元角色。**

我做这个项目，是想帮老婆把她的 IP 做成一个能说话、能互动的角色。开发过程中逐步加上了记忆、表情、配音和直播功能。现在把它整理成公开项目，方便有类似需求的人下载、使用和修改。

> 仓库随附的鲸鱼娘是有独立许可的社区演示形象，并非妻子的原创 IP，也不是 DeepSeek 官方角色。

## 一台电脑，完整运行

- **角色在本机**：Live2D 渲染、口型、表情、动作、空闲动画均在本地运行，无需 Vidu 等云端数字人渲染平台。
- **语音在本机**：Hojo TTS + ONNX Runtime 使用 CPU 合成，不需要云端配音服务，也不占用另一台 GPU 服务器。
- **角色可定制**：通过设置或自然语言调整名字、性格、说话方式和声线；本机保存角色记忆。
- **对话与表演联动**：根据语境安排情绪变化，强表情通过较弱表情逐步恢复，减少机械切换。
- **面向直播**：提供弹幕互动、过滤词、主播最高优先口播、直播状态和 OBS 浏览器画面地址。
- **Windows 桌面窗口**：承载聊天、角色与声音、直播工作台和独立直播画面；安装前检查显卡。

## 唯一必需的云端 AI 服务：DeepSeek

**使用者需要自行在 [DeepSeek 开放平台](https://platform.deepseek.com/) 创建账户、购买 API 额度并填写自己的 API Key。** 它用于角色对话，以及对话相关的语义、人设和表演规划；默认使用官方 Flash 入口并关闭深度思考，优先实时互动。角色渲染与语音合成均在本地。

密钥由 Windows DPAPI 加密保存在使用者电脑中；本项目不附带密钥、不代售额度。对话内容及用于生成回答的记忆会发送至 DeepSeek，因此这不是完全离线聊天软件。

抖音直播属于可选功能，仍需联网、直播权限和必要的登录态；OBS 或直播伴侣负责推流。它们不构成额外的云端角色渲染或配音服务。

## 开始使用

1. 从 [Releases](https://github.com/jouvies-ui/AI-Cartoon-Live/releases) 下载 Windows x64 安装包。
2. 在 Windows 10/11、配有 NVIDIA GTX 10 系列或更新显卡并安装正常驱动的电脑安装。建议至少 8 GB 内存、6 GB 可用磁盘空间，16 GB 内存更合适。
3. 首次启动填写自己的 DeepSeek API Key，然后进入聊天或角色设置。

内置 15 个 Hojo 40M 官方预置音色与 1 个 Hojo 80M 官方示例音色。未携带私人复刻声线、个人录音、历史对话、直播 Cookie 或开发服务器配置。安装后不依赖开发者的任何机器，无需另外安装 Python、CUDA 或 WSL。

## 文档

| 内容 | 简体中文 | English |
| --- | --- | --- |
| 安装、构建和排障 | [安装指南](docs/INSTALL.zh-CN.md) | [Installation](docs/INSTALL.en.md) |
| 架构、表情和数据流 | [架构说明](docs/ARCHITECTURE.zh-CN.md) | [Architecture](docs/ARCHITECTURE.en.md) |
| 隐私和数据管理 | [隐私说明](docs/PRIVACY.zh-CN.md) | [Privacy](docs/PRIVACY.en.md) |
| 项目进度与限制 | [当前状态](docs/STATUS.zh-CN.md) | [Status](docs/STATUS.en.md) |
| 第三方项目与作者 | [致谢](docs/THANKS.zh-CN.md) | [Acknowledgements](docs/THANKS.en.md) |
| 依赖清单 | [完整依赖](docs/DEPENDENCIES.zh-CN.md) | [Dependencies](docs/DEPENDENCIES.en.md) |
| 参与开发 | [贡献指南](docs/CONTRIBUTING.zh-CN.md) | [Contributing](docs/CONTRIBUTING.en.md) |

目前已完成代码、浏览器、CPU 模型、启动流程和安装包完整性检查；**Windows 真机安装与真实抖音直播仍待验证**。请按预览版本使用，并反馈具体问题。文档支持中英文切换，应用界面目前以中文为主。

## 感谢这些项目和作者

这个项目能做出来，是因为很多人已经把难的部分做了，并愿意公开分享。我们在他们的代码、模型和工具上继续开发，才做到了现在的本机角色、配音和直播互动。**没有他们，就没有 AI-Cartoon-Live 的最终落地。谢谢各位作者、维护者和贡献者。**

感谢抖音博主 **本草收藏**，他发布的视频为这个项目提供了最初的灵感。

### 直接使用的项目与工具

| 项目 | 作者或维护团队 | 本项目中的用途 |
| --- | --- | --- |
| [Cyber-xiaoya-live](https://github.com/cyber-xiaoya/cyber-xiaoya-live) | 天工开帧 / AI少女宇宙计划组 | 数字人应用、对话桥与直播交互的代码基础 |
| [Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light) | HojoAI | 40M/80M CPU 语音模型、推理代码和官方声音 |
| [dsh-whale-girl-live2d](https://github.com/Andersen216/dsh-whale-girl-live2d) | Andersen216 | 鲸鱼娘 Web 适配、模型清单与来源记录 |
| [douyinLive](https://github.com/jwwsjlm/douyinLive) | jwwsjlm | 本机抖音弹幕采集与签名 |
| [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) | guansss 及贡献者 / contributors | Live2D 模型在 PixiJS 中的显示 |
| [PixiJS](https://github.com/pixijs/pixijs) | PixiJS 团队及贡献者 / team and contributors | 本机 WebGL 渲染 |
| [Cubism Web Framework](https://github.com/Live2D/CubismWebFramework) | Live2D Inc. | Live2D 动画框架；Core 按独立 SDK 条款使用 |
| [Electron](https://github.com/electron/electron) | Electron 团队及贡献者 / team and contributors | 桌面窗口与平台集成 |
| [CPython](https://github.com/python/cpython) | Python Software Foundation 及贡献者 / contributors | 内置 Python 运行环境 |
| [ONNX](https://github.com/onnx/onnx) | ONNX 社区 / community | 模型格式与图处理 |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Microsoft 及贡献者 / contributors | CPU 推理和 INT8 优化 |
| [WeText](https://github.com/pengzhendong/wetext) | 彭振东 / Zhendong Peng 及贡献者 / contributors | 随包文字规范化与 WFST 资源 |
| [WeTextProcessing](https://github.com/wenet-e2e/WeTextProcessing) | WeNet 社区 / community | 文本规范化规则来源 |
| [kaldifst](https://github.com/k2-fsa/kaldifst) | k2-fsa 团队及贡献者 / team and contributors | FST 原生运行库 |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) | FFmpeg 开发者 / developers | 音频转换与处理 |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | ImageIO 团队及贡献者 / team and contributors | Windows FFmpeg 二进制分发 |
| [LIEF](https://github.com/lief-project/LIEF) | LIEF 开发者 / developers | 写入 Windows 可执行文件图标资源 |
| [Pillow](https://github.com/python-pillow/Pillow) | Pillow 开发者 / developers | 启动图标尺寸转换 |
| [NSIS](https://github.com/nsis-dev/nsis) | NSIS 开发者 / developers | Windows 安装器 |
| [Playwright](https://github.com/microsoft/playwright) | Microsoft 及贡献者 / contributors | 浏览器验证 |
| [OBS Studio](https://github.com/obsproject/obs-studio) | OBS Project 及贡献者 / contributors | 可选直播推流工具；不随本应用安装 |

### 鲸鱼娘的三位创作者

| 作者 | 创作贡献 |
| --- | --- |
| [上善无形](https://space.bilibili.com/4456176) | 原创角色「溟月」 / Original character “Mingyue” |
| [ZipZipPipe](https://space.bilibili.com/4168597) | 女仆鲸鱼娘二次设计 / Whale-girl maid redesign |
| [氵六青](https://space.bilibili.com/11272072) | Live2D 建模、绑定、表情与动作 / Live2D model, rigging, expressions and motions |

Andersen216 整理了模型的 Web 适配与来源信息。我们保留其署名、上游许可和原始使用说明。当前启动图标来自模型的实际渲染画面，做了头像裁切、圆角和多尺寸 ICO 转换；本项目另补充了部分表情文件和本地控制逻辑。

### 间接依赖与参考

- 完整 Python 依赖逐项列在 [依赖清单](docs/DEPENDENCIES.zh-CN.md)，包括 FastAPI、Uvicorn、Starlette、HTTPX、WebSockets、NumPy、SciPy、librosa 等 67 个安装包。感谢各项目作者及所有贡献者，逐项附有源仓库链接。
- [Cyber-xiaoya-danmaku](https://github.com/cyber-xiaoya/cyber-xiaoya-danmaku)（天工开帧）提供了上游弹幕接入参考；本发行版实际内置的是 douyinLive，不打包该采集器。
- Hojo 上游特别致谢了 [X-Codec-2.0](https://github.com/zhenye234/X-Codec-2.0)（zhenye234）、[Soprano](https://github.com/ekwek1/soprano)（ekwek1）、[Inworld TTS](https://github.com/inworld-ai/tts)（Inworld AI）。这里继续保留这条致谢，不把上游研究成果算作我们的工作。
- Electron 包含 [Chromium](https://chromium.googlesource.com/chromium/src/) 及其第三方组件；Python、ONNX Runtime、FFmpeg 等也包含底层依赖。它们的完整许可随官方二进制分发，并在安装包中保留。
- 感谢 [OpenBLAS](https://github.com/OpenMathLib/OpenBLAS)、[LLVM](https://github.com/llvm/llvm-project)、[libsndfile](https://github.com/libsndfile/libsndfile)、[libsoxr](https://sourceforge.net/projects/soxr/)、[Kaldi](https://github.com/kaldi-asr/kaldi)、[OpenFst](https://www.openfst.org/) 的开发者提供底层计算、音频与 FST 能力；具体组合以所附依赖许可为准。

### 开发支持

感谢 **[CodeX](https://openai.com/codex/)** 在快速开发过程中提供的帮助，包括代码实现、问题排查、测试、打包和文档整理。工具支持与上游项目的作者贡献分别记录；本项目的 Git 提交使用维护者自己的身份。

### 许可边界

- 本项目及对 Cyber-xiaoya-live 的代码修改按 [AGPL-3.0](LICENSE) 发布；原作者署名保留在 [上游 NOTICE](source/repo/NOTICE)。上游原有人物、私有声线、内容素材和品牌标识没有因此获得再分发许可，也未作为本项目演示内容打包。
- Hojo 部分按 Apache-2.0，鲸鱼娘 Web 适配按 MIT，其他运行库按各自条款。项目名、公开仓库或致谢都不覆盖这些许可。
- 鲸鱼娘美术素材遵循 **CC BY-NC-SA 4.0**：署名、非商业、相同方式共享。用于带货、广告、收费服务或商业 IP 前，需要自行取得相应授权或换用自己拥有权利的形象。
- Live2D Cubism Core 是 Live2D Inc. 的专有可再分发运行库，依照 [官方 SDK 协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html) 使用；不是 MIT 或 AGPL 代码。
- 原始法律许可文件按原文保留；中文和英文说明不能代替原许可证。若发现署名遗漏，请提交具体文件和来源，我们会核对补充。
