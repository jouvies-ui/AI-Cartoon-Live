# Thanks to the projects and people behind this work

[简体中文](THANKS.zh-CN.md) | [English](THANKS.en.md) | [AI-Cartoon-Live](../README.md)

This project exists because other people solved difficult problems and shared their work. Their code, models and tools made it possible for us to build local characters, speech and live interaction. **Without them, AI-Cartoon-Live would not have become a working project. Thank you to the authors, maintainers and contributors.**

## Projects and tools we use

| Project | Author or maintainers | Use in this project |
| --- | --- | --- |
| [Cyber-xiaoya-live](https://github.com/cyber-xiaoya/cyber-xiaoya-live) | 天工开帧 / AI少女宇宙计划组 | Application, dialogue bridge and live-interaction foundation |
| [Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light) | HojoAI | 40M/80M CPU speech models, inference code and official voices |
| [dsh-whale-girl-live2d](https://github.com/Andersen216/dsh-whale-girl-live2d) | Andersen216 | Whale-girl web integration, model manifest and provenance |
| [douyinLive](https://github.com/jwwsjlm/douyinLive) | jwwsjlm | Local Douyin collection and request signing |
| [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) | guansss 及贡献者 / contributors | Displaying Live2D models in PixiJS |
| [PixiJS](https://github.com/pixijs/pixijs) | PixiJS 团队及贡献者 / team and contributors | Local WebGL rendering |
| [Cubism Web Framework](https://github.com/Live2D/CubismWebFramework) | Live2D Inc. | Live2D animation framework; Core has separate SDK terms |
| [Electron](https://github.com/electron/electron) | Electron 团队及贡献者 / team and contributors | Desktop windows and platform integration |
| [CPython](https://github.com/python/cpython) | Python Software Foundation 及贡献者 / contributors | Embedded Python runtime |
| [ONNX](https://github.com/onnx/onnx) | ONNX 社区 / community | Model format and graph processing |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Microsoft 及贡献者 / contributors | CPU inference and INT8 optimization |
| [WeText](https://github.com/pengzhendong/wetext) | 彭振东 / Zhendong Peng 及贡献者 / contributors | Bundled text normalization and WFST resources |
| [WeTextProcessing](https://github.com/wenet-e2e/WeTextProcessing) | WeNet 社区 / community | Source of text-normalization rules |
| [kaldifst](https://github.com/k2-fsa/kaldifst) | k2-fsa 团队及贡献者 / team and contributors | Native FST runtime |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) | FFmpeg 开发者 / developers | Audio conversion and processing |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | ImageIO 团队及贡献者 / team and contributors | Windows FFmpeg distribution |
| [LIEF](https://github.com/lief-project/LIEF) | LIEF 开发者 / developers | Windows executable icon resources |
| [Pillow](https://github.com/python-pillow/Pillow) | Pillow 开发者 / developers | Launcher icon resizing |
| [NSIS](https://github.com/nsis-dev/nsis) | NSIS 开发者 / developers | Windows installer |
| [Playwright](https://github.com/microsoft/playwright) | Microsoft 及贡献者 / contributors | Browser verification |
| [OBS Studio](https://github.com/obsproject/obs-studio) | OBS Project 及贡献者 / contributors | Optional broadcasting tool; not installed by this app |

## The three whale-girl artists

| Artist | Contribution |
| --- | --- |
| [上善无形](https://space.bilibili.com/4456176) | 原创角色「溟月」 / Original character “Mingyue” |
| [ZipZipPipe](https://space.bilibili.com/4168597) | 女仆鲸鱼娘二次设计 / Whale-girl maid redesign |
| [氵六青](https://space.bilibili.com/11272072) | Live2D 建模、绑定、表情与动作 / Live2D model, rigging, expressions and motions |

Andersen216 assembled the model's web integration and provenance. We retain the credits, licenses and original usage notice. The launcher icon is cropped from an actual model render, with rounded corners and multiple ICO sizes. This project also adds some expression files and local control logic.

## Dependencies and references

- The [dependency inventory](DEPENDENCIES.en.md) lists all 67 installed Python packages, including FastAPI, Uvicorn, Starlette, HTTPX, WebSockets, NumPy, SciPy and librosa. Each entry links to its source and credits its maintainers and contributors.
- [Cyber-xiaoya-danmaku](https://github.com/cyber-xiaoya/cyber-xiaoya-danmaku), by 天工开帧, supplied the upstream comment-integration reference. This release bundles douyinLive, not that collector.
- Hojo acknowledges [X-Codec-2.0](https://github.com/zhenye234/X-Codec-2.0) by zhenye234, [Soprano](https://github.com/ekwek1/soprano) by ekwek1, and [Inworld TTS](https://github.com/inworld-ai/tts) by Inworld AI. We carry those acknowledgements forward rather than presenting upstream research as our own.
- Electron includes [Chromium](https://chromium.googlesource.com/chromium/src/) and its third-party components. Python, ONNX Runtime and FFmpeg also contain lower-level dependencies. Their complete notices accompany official binaries and are retained in the installer.
- Thanks also to the developers of [OpenBLAS](https://github.com/OpenMathLib/OpenBLAS), [LLVM](https://github.com/llvm/llvm-project), [libsndfile](https://github.com/libsndfile/libsndfile), [libsoxr](https://sourceforge.net/projects/soxr/), [Kaldi](https://github.com/kaldi-asr/kaldi) and [OpenFst](https://www.openfst.org/) for computation, audio and FST foundations. Exact bundled combinations are documented by the included dependency licenses.

## Development support

Thank you to **[CodeX](https://openai.com/codex/)** for support during rapid development, including implementation, troubleshooting, testing, packaging and documentation. Tool assistance and upstream authorship are credited separately. Git commits use the maintainer's own identity.

## License boundaries

- This project and its modifications to Cyber-xiaoya-live are distributed under [AGPL-3.0](../LICENSE). Original attribution is retained in the [upstream NOTICE](../source/repo/NOTICE). This does not grant redistribution rights to upstream characters, private voices, content assets or branding; those are not included as this project's demo content.
- Hojo components use Apache-2.0, the whale-girl web adaptation uses MIT, and other libraries retain their own terms. Neither this project name nor an acknowledgement overrides a license.
- Whale-girl artwork is **CC BY-NC-SA 4.0**: attribution, non-commercial use and share-alike. Obtain appropriate permission or use artwork you own before commercial streaming, advertising, paid services or commercial IP use.
- Live2D Cubism Core is a proprietary redistributable runtime from Live2D Inc., used under the [official SDK agreement](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html). It is not MIT or AGPL code.
- Original legal texts remain unchanged. English and Chinese explanations do not replace licenses. If a credit is missing, report the file and source so we can check and correct it.
