# 安装、构建与排障

[简体中文](INSTALL.zh-CN.md) | [English](INSTALL.en.md) | [AI-Cartoon-Live](../README.md)

## 安装

从 [Releases](https://github.com/jouvies-ui/AI-Cartoon-Live/releases) 下载安装器并核对附带的 SHA256。要求 Windows 10/11 x64、正常驱动的 NVIDIA GTX 10 系或更新显卡。安装前检查计算能力至少 6.1，旧驱动使用型号辅助判断；仅检查硬件门槛，不代表所有机器的性能都相同。

角色使用 GPU 渲染，TTS 在 CPU 上运行。建议 8 GB 以上内存（推荐 16 GB）和 6 GB 可用磁盘空间。安装器内置运行时及模型，无需 Python、CUDA 或 WSL；首次启动需联网验证自己的 DeepSeek API Key。新版本覆盖安装会保留本机设置与记忆。

Windows 可显示“未知发布者”，因为安装器尚未使用商业代码签名证书签名。Windows 真机安装仍待验证，当前为预览版。

## 对话与直播

进入“角色与声音”选择官方声线、调整名字和性格。自动回答最多 50 字；50 字内按一段合成，减少句间停顿。主播优先口播可打断当前自动回答，播完后恢复互动队列。

在直播工作台填写抖音直播间链接；平台要求登录时输入自己的 Cookie。先用模拟弹幕验证，再验证真实房间。独立直播画面可以作为同机 OBS 浏览器来源；实际开播需直播权限，应用不会替用户公开开播。

## 从源码构建

当前构建流程以 macOS/Linux 主机生成 Windows x64 NSIS 安装包。Windows 原生构建流程尚未验证。需要 Python 3.12、NSIS（`makensis` 在 PATH）、联网能力及足够缓存空间。

默认缓存位于系统临时目录 `ai-cartoon-live-build`，可通过 `AI_CARTOON_BUILD_DIR` 指定绝对路径。它仅用于构建；运行时不依赖这个目录。

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

80M INT8 图使用锁定的 ONNX Runtime 1.21.1 生成。优化图按已记录的哈希校验，不同平台或工具版本可能产生不同图；遇到不一致应先验证推理输出并审查，不要删除校验。原模型始终保留。

模型和二进制不进入 Git；构建产物写入 `release/`。`distribution-files.json` 锁定源文件和素材，构建不会自动扩充白名单。修改需要审查后更新相应哈希，新增素材必须有来源和再分发权利。

## 检查

```sh
python verify_unicode_startup.py
python verify_portable.py
python verify_startup_diagnostics.py
python distribution_audit.py --app "$(python -c 'from build_paths import WORK; print(WORK / "app")')"
```

界面检查需另行安装 Playwright，并启动隔离测试服务：`npm install --no-save playwright`、`npx playwright install chromium`，然后按测试脚本说明运行 `node verify_ui.cjs`。可用 `AI_CARTOON_TEST_URL` 指定测试服务地址。

## 排障

点击“服务日志”，查看 `%APPDATA%\WhaleCompanion` 下的 `launcher.log` 及 `logs/40m.log`、`logs/80m.log`。资源路径兼容中文与空格；服务加载前执行中英文文字处理自检。端口冲突会自动选择可用端口。关闭主窗口会停止本应用的子进程。

数据目录与可执行文件保留历史内部名称 `WhaleCompanion`，用于兼容早期独立版本。它不是外部服务或开发机器。卸载保留本机数据；清空前请自行备份。
