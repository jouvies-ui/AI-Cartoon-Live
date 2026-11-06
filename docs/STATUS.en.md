# Project status

[简体中文](STATUS.zh-CN.md) | [English](STATUS.en.md) | [AI-Cartoon-Live](../README.md)

As of 2026-11-06. Public preview: 0.1.3, based on the audited standalone 0.1.2.

Implemented: local whale-girl rendering/icons, contextual expressions, persona and memory, official voice library, CPU ONNX speech, DeepSeek first-run setup, live studio, word filters, priority host announcements, and Windows installer.

Checked: host-side APIs, browser Live2D rendering, CPU speech models, Unicode-path adaptation, service lifecycle, file allowlists, official sample/model hashes, and full installer extraction consistency. These checks do not validate every feature on every machine.

Still unverified: installation on physical Windows hardware, NVIDIA driver detection, native DLL loading, DPAPI, the user's DeepSeek account, and real Douyin streaming. Production streaming acceptance has not been claimed. The UI is primarily Chinese; this release adds bilingual documentation.

0.1.3: public project branding, bilingual docs, acknowledgements and dependency inventory, removal of developer-tool absolute paths, configurable build cache. Retains 0.1.2 local behavior and data compatibility.

0.1.2: locked file allowlists and asset hashes; excludes runtime data, private voices and credentials.

0.1.1: fixed text-normalization loading under Chinese installation paths, added startup preflight and unified whale-girl icons.
