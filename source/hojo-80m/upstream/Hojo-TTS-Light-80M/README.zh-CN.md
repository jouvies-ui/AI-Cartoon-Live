# Hojo-TTS-Light 80M 本地集成说明

[简体中文](README.zh-CN.md) | [English](README.md)

本目录保留 HojoAI 的 80M ONNX 推理代码；[英文原始说明](README.md) 保留上游用法与技术细节。完整原仓库见 [HojoAI/Hojo-TTS-Light](https://github.com/HojoAI/Hojo-TTS-Light/tree/7b2c674b0b02a979670a9496c9ed471ff99c05cf/Hojo-TTS-Light-80M)。

AI-Cartoon-Live 使用随附服务适配器运行 CPU 语音，安装后的路径由启动器指定。模型按 `model-manifest.json` 下载并校验，文件不进入 Git。40M 提供官方预置音色；80M 使用官方 zh1 示例参考音频，不带私人录音。

`text_normalize.py` 改为使用随包 WeText/kaldifst，语音进程固定工作目录，使用 ASCII 相对路径读取 FST，以兼容 Windows 中文安装路径。应用入口与安装步骤见[中文安装指南](../../../../docs/INSTALL.zh-CN.md)。

感谢 HojoAI 及上游研究作者。许可为 [Apache-2.0](../../LICENSE.txt)。英文原文中提到的 infer.py 等工具属于完整上游项目，不全部随本精简集成提供。
