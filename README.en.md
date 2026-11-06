# AI-Cartoon-Live

**[简体中文](README.md) | [English](README.en.md)**

<img src="assets/whale.png" alt="Whale-girl demo character" width="160">

**Run an anime character with dialogue, memory, expressions and live interaction on one local computer with an NVIDIA GPU.**

I started this project to help my wife turn her character IP into something people could talk to and interact with. Memory, expressions, speech and streaming were added along the way. I am sharing it so others with similar needs can use it and make their own changes.

> The bundled whale-girl is a separately licensed community demo asset. It is neither the wife's original IP nor an official DeepSeek character.

## One computer, a complete local character

- **Local character rendering:** Live2D, lip movement, expressions, motions, and idle animation run on the user's computer without Vidu or a cloud avatar renderer.
- **Local speech:** Hojo TTS with ONNX Runtime synthesizes on the CPU, without a cloud voice service or a separate GPU server.
- **Customizable persona:** Change the name, personality, speaking style, and voice through settings or natural language. Character memory is stored locally.
- **Contextual performance:** Dialogue informs emotion changes, with softer transitions after strong expressions to reduce mechanical switching.
- **Live interaction:** Comment responses, word filters, highest-priority host announcements, visible status, and an OBS browser-source URL.
- **Windows desktop:** Chat, character/voice settings, a live studio, and a separate broadcast window, with a GPU check before installation.

## The only required cloud AI service: DeepSeek

**Users must create their own account at the [DeepSeek platform](https://platform.deepseek.com/), purchase API credit, and enter their own API Key.** It powers character dialogue and related semantic, persona, and performance planning. The default uses the official Flash endpoint with thinking disabled for interactive responses. Avatar rendering and speech synthesis run locally.

Windows DPAPI encrypts the key on the user's computer. This project supplies no keys and does not resell credit. Conversation text and the memory needed to produce an answer are sent to DeepSeek; this is not fully offline chat.

Douyin streaming is optional and still needs internet access, platform permission, and any required login state. OBS or the platform's broadcasting software handles streaming. These are not additional cloud avatar or TTS services.

## Get started

1. Download the Windows x64 installer from [Releases](https://github.com/jouvies-ui/AI-Cartoon-Live/releases).
2. Install on Windows 10/11 with a working NVIDIA GTX 10-series-or-newer GPU and driver. Allow at least 8 GB RAM and 6 GB free disk space; 16 GB RAM is recommended.
3. Enter your own DeepSeek API Key on first launch, then open chat or character settings.

The package includes 15 official Hojo 40M presets and one official Hojo 80M example voice. It contains no private cloned voices, personal recordings, chat history, streaming cookies, or development-server configuration. No developer machine, separately installed Python, CUDA, or WSL is required after installation.

## Documentation

| Topic | 简体中文 | English |
| --- | --- | --- |
| Install, build, troubleshoot | [安装指南](docs/INSTALL.zh-CN.md) | [Installation](docs/INSTALL.en.md) |
| Architecture and data flow | [架构说明](docs/ARCHITECTURE.zh-CN.md) | [Architecture](docs/ARCHITECTURE.en.md) |
| Privacy and local data | [隐私说明](docs/PRIVACY.zh-CN.md) | [Privacy](docs/PRIVACY.en.md) |
| Status and limitations | [当前状态](docs/STATUS.zh-CN.md) | [Status](docs/STATUS.en.md) |
| Projects and authors | [致谢](docs/THANKS.zh-CN.md) | [Acknowledgements](docs/THANKS.en.md) |
| Full dependency inventory | [完整依赖](docs/DEPENDENCIES.zh-CN.md) | [Dependencies](docs/DEPENDENCIES.en.md) |
| Contributing | [贡献指南](docs/CONTRIBUTING.zh-CN.md) | [Contributing](docs/CONTRIBUTING.en.md) |

Code, browser rendering, CPU models, startup flow, and installer integrity have been checked. **Installation on physical Windows hardware and real Douyin streaming remain unverified.** Treat this as a preview and report concrete issues. Documentation supports both languages; the app UI is currently primarily Chinese.

## Thanks and licensing

**Without these open-source projects and their authors, AI-Cartoon-Live would not have become a working project.** Special thanks to [Cyber-xiaoya-live](https://github.com/cyber-xiaoya/cyber-xiaoya-live), [Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light), [dsh-whale-girl-live2d](https://github.com/Andersen216/dsh-whale-girl-live2d), [douyinLive](https://github.com/jwwsjlm/douyinLive), and every contributor represented in the [acknowledgements](docs/THANKS.en.md) and [dependency inventory](docs/DEPENDENCIES.en.md).

Thank you also to **[CodeX](https://openai.com/codex/)** for rapid-development support with implementation, troubleshooting, testing and packaging.

Source code is distributed under [AGPL-3.0](LICENSE) and retained third-party terms. Whale-girl artwork by 上善无形, ZipZipPipe, and 氵六青 is **CC BY-NC-SA 4.0, for non-commercial use under its terms**. Live2D Cubism Core has separate proprietary SDK terms. Publishing source does not grant commercial artwork rights. This is an independent derivative, not an official product of upstream authors or platforms. See [license boundaries](docs/THANKS.en.md#license-boundaries).
