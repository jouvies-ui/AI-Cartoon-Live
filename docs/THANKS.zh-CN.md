# 感谢这些项目和作者

[简体中文](THANKS.zh-CN.md) | [English](THANKS.en.md) | [AI-Cartoon-Live](../README.md)

这个项目能做出来，是因为很多人已经把难的部分做了，并愿意公开分享。我们在他们的代码、模型和工具上继续开发，才做到了现在的本机角色、配音和直播互动。**没有他们，就没有 AI-Cartoon-Live 的最终落地。谢谢各位作者、维护者和贡献者。**

感谢抖音博主 **本草收藏**，他发布的视频为这个项目提供了最初的灵感。

## 直接使用的项目与工具

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

## 鲸鱼娘的三位创作者

| 作者 | 创作贡献 |
| --- | --- |
| [上善无形](https://space.bilibili.com/4456176) | 原创角色「溟月」 / Original character “Mingyue” |
| [ZipZipPipe](https://space.bilibili.com/4168597) | 女仆鲸鱼娘二次设计 / Whale-girl maid redesign |
| [氵六青](https://space.bilibili.com/11272072) | Live2D 建模、绑定、表情与动作 / Live2D model, rigging, expressions and motions |

Andersen216 整理了模型的 Web 适配与来源信息。我们保留其署名、上游许可和原始使用说明。当前启动图标来自模型的实际渲染画面，做了头像裁切、圆角和多尺寸 ICO 转换；本项目另补充了部分表情文件和本地控制逻辑。

## 间接依赖与参考

- 完整 Python 依赖逐项列在 [依赖清单](DEPENDENCIES.zh-CN.md)，包括 FastAPI、Uvicorn、Starlette、HTTPX、WebSockets、NumPy、SciPy、librosa 等 67 个安装包。感谢各项目作者及所有贡献者，逐项附有源仓库链接。
- [Cyber-xiaoya-danmaku](https://github.com/cyber-xiaoya/cyber-xiaoya-danmaku)（天工开帧）提供了上游弹幕接入参考；本发行版实际内置的是 douyinLive，不打包该采集器。
- Hojo 上游特别致谢了 [X-Codec-2.0](https://github.com/zhenye234/X-Codec-2.0)（zhenye234）、[Soprano](https://github.com/ekwek1/soprano)（ekwek1）、[Inworld TTS](https://github.com/inworld-ai/tts)（Inworld AI）。这里继续保留这条致谢，不把上游研究成果算作我们的工作。
- Electron 包含 [Chromium](https://chromium.googlesource.com/chromium/src/) 及其第三方组件；Python、ONNX Runtime、FFmpeg 等也包含底层依赖。它们的完整许可随官方二进制分发，并在安装包中保留。
- 感谢 [OpenBLAS](https://github.com/OpenMathLib/OpenBLAS)、[LLVM](https://github.com/llvm/llvm-project)、[libsndfile](https://github.com/libsndfile/libsndfile)、[libsoxr](https://sourceforge.net/projects/soxr/)、[Kaldi](https://github.com/kaldi-asr/kaldi)、[OpenFst](https://www.openfst.org/) 的开发者提供底层计算、音频与 FST 能力；具体组合以所附依赖许可为准。

## 开发支持

感谢 **[CodeX](https://openai.com/codex/)** 在快速开发过程中提供的帮助，包括代码实现、问题排查、测试、打包和文档整理。工具支持与上游项目的作者贡献分别记录；本项目的 Git 提交使用维护者自己的身份。

## 许可边界

- 本项目及对 Cyber-xiaoya-live 的代码修改按 [AGPL-3.0](../LICENSE) 发布；原作者署名保留在 [上游 NOTICE](../source/repo/NOTICE)。上游原有人物、私有声线、内容素材和品牌标识没有因此获得再分发许可，也未作为本项目演示内容打包。
- Hojo 部分按 Apache-2.0，鲸鱼娘 Web 适配按 MIT，其他运行库按各自条款。项目名、公开仓库或致谢都不覆盖这些许可。
- 鲸鱼娘美术素材遵循 **CC BY-NC-SA 4.0**：署名、非商业、相同方式共享。用于带货、广告、收费服务或商业 IP 前，需要自行取得相应授权或换用自己拥有权利的形象。
- Live2D Cubism Core 是 Live2D Inc. 的专有可再分发运行库，依照 [官方 SDK 协议](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html) 使用；不是 MIT 或 AGPL 代码。
- 原始法律许可文件按原文保留；中文和英文说明不能代替原许可证。若发现署名遗漏，请提交具体文件和来源，我们会核对补充。
