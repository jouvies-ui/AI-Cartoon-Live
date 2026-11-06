# Privacy and local data

[简体中文](PRIVACY.zh-CN.md) | [English](PRIVACY.en.md) | [AI-Cartoon-Live](../README.md)

- DeepSeek receives current dialogue, relevant conversation memory and persona prompts to generate answers and associated plans. Billing and data handling are between the user and DeepSeek.
- Persona, memory, voice selection and logs live under `%APPDATA%\WhaleCompanion`. Windows DPAPI encrypts the API Key. It is passed only to the local dialogue service, not to the web UI or TTS services.
- Live2D and Hojo speech run locally. Installers contain no private voices, personal recordings, previous memories or account credentials.
- Optional Douyin collection connects to Douyin and processes public room interactions; the platform may require a cookie. Never upload cookies, keys or a full user-data directory to GitHub.
- Closing the window stops its services. Uninstalling preserves data; back it up before removing it. Upgrading does not automatically erase existing settings.

Report only redacted error excerpts, version, OS and hardware details. Native-library and driver behavior still needs testing on Windows.
