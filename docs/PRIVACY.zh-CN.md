# 隐私与本机数据

[简体中文](PRIVACY.zh-CN.md) | [English](PRIVACY.en.md) | [AI-Cartoon-Live](../README.md)

- DeepSeek 收到当前对话、必要的上下文记忆和角色提示，用于生成回答及相关计划。购买额度与数据处理政策由用户和 DeepSeek 之间约定。
- 人设、记忆、声音选择与日志保存在 `%APPDATA%\WhaleCompanion`；API Key 由 Windows DPAPI 加密保存，只传给本机对话服务，不发送给网页或语音服务。
- Live2D 与 Hojo 语音在本机运行。安装包没有私有声线、个人录音、历史记忆或账号凭据。
- 可选抖音采集需要访问抖音并处理直播间公开互动信息；平台可能要求 Cookie。请勿把 Cookie、密钥或完整用户目录上传至 GitHub。
- 用户关闭窗口时后台服务一并停止。卸载保留数据；可先备份再自行清空。覆盖安装不会自动清空已有设置。

反馈问题时，只提交脱敏后的报错片段、版本、系统和硬件信息。依赖原生库或显卡驱动的行为仍需 Windows 实测。
