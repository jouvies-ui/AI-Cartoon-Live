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

## 感谢与许可

**没有这些开源项目及作者的工作，就没有 AI-Cartoon-Live 最终落地。** 特别感谢 [Cyber-xiaoya-live](https://github.com/cyber-xiaoya/cyber-xiaoya-live)、[Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light)、[dsh-whale-girl-live2d](https://github.com/Andersen216/dsh-whale-girl-live2d)、[douyinLive](https://github.com/jwwsjlm/douyinLive)，以及 [完整致谢列表](docs/THANKS.zh-CN.md) 和 [依赖清单](docs/DEPENDENCIES.zh-CN.md) 中的每一位贡献者。

同时感谢 **[CodeX](https://openai.com/codex/)** 提供快速开发支持，帮助完成代码、排障、测试和打包。

源代码按 [AGPL-3.0](LICENSE) 及保留的第三方许可发布。鲸鱼娘美术素材由上善无形、ZipZipPipe、氵六青创作，采用 **CC BY-NC-SA 4.0，仅限符合条款的非商业使用**；Live2D Cubism Core 有独立的专有 SDK 条款。公开源码不等于获得素材商业授权。项目不与上游作者或平台存在官方隶属关系，详见 [许可说明](docs/THANKS.zh-CN.md#许可边界)。
