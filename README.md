# TokenView ⚡

> **A Lightweight, Non-Intrusive Desktop Quota & Token Monitor for AI Developers & Agent Frameworks.**  
> Real-time status, multi-account quota tracking, and rate-limit guard for **OpenAI Codex**, **Antigravity (Gemini)**, and **DeepSeek**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)](https://microsoft.com/windows)

---

## 🌟 Overview

When building applications with large language models and autonomous coding agents (such as OpenAI Codex), developers frequently encounter unexpected rate limits, token exhaustion, and silent context overflows. 

**TokenView** is engineered to solve this developer friction by providing a real-time, non-intrusive desktop floating capsule that displays exact token consumption and remaining account quotas without interrupting active workflows.

### Key Highlights
- **Seamless OpenAI Codex Integration**: Native discovery and tracking of local Codex CLI sessions, remaining 5-hour/weekly quotas, and account limits.
- **Multi-Account & Multi-Provider Support**: Unified dashboard across OpenAI Codex, Antigravity (Gemini), and DeepSeek accounts.
- **Ultra-Lightweight Native Architecture**: Built on pure Python and native Windows WinForms (via `pythonnet`). Zero Electron overhead, consuming minimal memory (<25MB) and negligible CPU.
- **Local-First Security Boundary**: 
  - Zero cloud relays or third-party telemetry.
  - Sensitive credentials and keys are strictly encrypted using the Windows Data Protection API (DPAPI) tied to the current local user.
- **Adaptive Floating Capsule**: Floats quietly alongside active IDE / Agent workspaces, auto-expands on hover, and adapts to theme luminance dynamically.

---

## 📸 Interface Preview

```
+--------------------------------------------------------------+
| [O] Codex (Pro)     | 78% [||||||||||....] | Reset in 2h 15m |
| [G] Antigravity     | 92% [||||||||||||..] | Active Tier     |
| [D] DeepSeek        | $14.28 Balance       | Fast API        |
+--------------------------------------------------------------+
```
*(Interactive collapsible capsule with smooth fade-in/out and customizable threshold alerts)*

---

## 🚀 Quick Start

### Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.10 or higher
- Optional: OpenAI Codex CLI / Antigravity CLI / DeepSeek API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/TokenView.git
   cd TokenView
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch TokenView:**
   ```bash
   python main.py
   ```

---

## ⚙️ Configuration & Architecture

### Provider Support
1. **OpenAI Codex**: Automatically detects local authenticated sessions and fetches live quota summaries. Supports adding multiple isolated developer accounts with separate workspace roots.
2. **DeepSeek**: Real-time official balance and grant balance inquiry, securely encrypted via Windows DPAPI.
3. **Antigravity**: Validates matching local session identities and displays 5H/Weekly capacity rings.

### Project Structure
```
TokenView/
├── tokenview/          # Core Python modules
│   ├── ui.py           # WinForms native UI layout and components
│   ├── providers.py    # Quota fetching and CLI RPC handlers
│   ├── store.py        # Local encrypted state and settings management
│   ├── native.py       # Windows Win32 API interop and DPAPI encryption
│   └── visual.py       # Render loops, animations, and color management
├── main.py             # Application entrypoint
├── requirements.txt    # Runtime dependencies
├── LICENSE             # MIT License
└── README.md           # Documentation
```

---

## 🛡️ Security & Privacy

- **No Remote Telemetry**: TokenView communicates solely with the official API endpoints or local CLI pipes configured by the user.
- **Safe Quota Inspection**: Read-only queries to quota/balance APIs; never executes unauthorized model inferences or data collection.
- **Zero Plaintext Secrets**: Custom keys are protected using Windows DPAPI machine/user scope encryption.

---

## 🤝 Contributing & Community

Contributions are warmly welcomed! Please feel free to open Issues for bug reports, feature suggestions, or submit Pull Requests.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<details>
<summary><b>🇨🇳 中文说明 (Click to expand)</b></summary>

### 简介
**TokenView** 是一款专为 AI 开发者与智能体（Agent）工作流打造的 Windows 轻量级桌面额度监控悬浮工具。支持实时追踪 **OpenAI Codex**、**Antigravity (Gemini)** 和 **DeepSeek** 的账户额度与 Token 消耗情况。

### 核心特性
- **轻量原生**：基于 Python + WinForms，内存占用极低，告别臃肿的 Electron 包装。
- **安全本地优先**：凭据由 Windows 本地 DPAPI 加密存储，无任何第三方云端中转。
- **智能悬浮交互**：智能吸附在 IDE 或 Agent 窗口顶栏，悬停展开完整卡片，离开自动轻量收起。
- **多账号管理**：支持多 Codex 账号、多 DeepSeek Key 的独立额度与余额追踪。

</details>
