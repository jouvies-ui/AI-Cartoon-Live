# Installation, build and troubleshooting

[简体中文](INSTALL.zh-CN.md) | [English](INSTALL.en.md) | [AI-Cartoon-Live](../README.md)

## Installation

Download an installer and its SHA256 file from [Releases](https://github.com/jouvies-ui/AI-Cartoon-Live/releases). Windows 10/11 x64 and a working NVIDIA GTX 10-series-or-newer driver/GPU are required. The installer checks compute capability of at least 6.1, with a model-name fallback for older drivers. This is a hardware gate, not a performance guarantee.

The GPU renders the character; TTS runs on the CPU. Allow at least 8 GB RAM (16 GB recommended) and 6 GB free disk space. Runtimes and models are bundled: no separate Python, CUDA, or WSL is needed. First launch needs internet to validate your DeepSeek key. Installing over an earlier version preserves local settings and memory.

Windows may display “Unknown publisher”: the installer is not commercially code-signed. Physical Windows installation is still unverified; this is a preview.

## Chat and streaming

Choose an official voice and edit the name/personality in character settings. Automatic answers are capped at 50 Chinese characters; answers within that length are synthesized together to avoid sentence gaps. A host-priority announcement interrupts the current automatic response and then resumes the interaction queue.

Enter a Douyin room URL in the studio and your own cookie if login is required. Start with simulated comments, then test a real room. Add the separate broadcast page to OBS on the same computer. Streaming requires your own platform permission; the app does not start a public broadcast for you.

## Build from source

The current workflow builds Windows x64 NSIS installers on macOS/Linux. Native Windows building is not verified. Install Python 3.12 and NSIS (`makensis` on PATH), and provide internet access and cache space.

The default cache is `ai-cartoon-live-build` under the system temporary directory. Override it with an absolute `AI_CARTOON_BUILD_DIR`. It is used only for building, never as a runtime dependency.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-build.txt
python fetch_runtime.py
python -m pip download --platform win_amd64 --python-version 3.12 --implementation cp --only-binary=:all: --dest "$(python -c 'from build_paths import WORK; print(WORK / "wheels")')" --require-hashes -r requirements-windows.lock
python fetch_models.py
python quantize_model.py
python build.py
```

The 80M INT8 graph is generated with pinned ONNX Runtime 1.21.1 and checked against the recorded hash. Different platforms/tool versions may generate a different graph; verify inference and review it before accepting a new hash. Do not remove the check. Original models remain intact.

Models and binaries stay outside Git; outputs go into `release/`. `distribution-files.json` locks source and artwork inputs. Builds never expand the allowlist automatically. Review changes before updating hashes and document redistribution rights for new assets.

## Checks

```sh
python verify_unicode_startup.py
python verify_portable.py
python verify_startup_diagnostics.py
python distribution_audit.py --app "$(python -c 'from build_paths import WORK; print(WORK / "app")')"
```

For UI checks, install Playwright (`npm install --no-save playwright`, `npx playwright install chromium`), start an isolated test service, then run `node verify_ui.cjs`. `AI_CARTOON_TEST_URL` overrides its service URL.

## Troubleshooting

Use “Service logs” to open `launcher.log` and `logs/40m.log` or `logs/80m.log` under `%APPDATA%\WhaleCompanion`. Chinese and spaced paths are supported; both languages are checked before model loading. Ports automatically fall back when occupied. Closing the main window stops the app's children.

The executable and data folder retain the internal name `WhaleCompanion` for compatibility with earlier standalone versions. It is not a cloud service or a developer-machine dependency. Uninstalling preserves local data; back it up before removing it yourself.
