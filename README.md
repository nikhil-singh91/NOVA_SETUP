# NOVA

Personal AI Companion

Version: v5

Status: Under Development



# NOVA

**NOVA — Your Personal AI Operating System.A modular, emotionally intelligent, voice-first AI companion capable of reasoning, remembering, searching, automating, and controlling your computer.**

NOVA is not a chatbot. NOVA is a modular, extensible AI companion system designed to integrate multiple AI providers, real-time data sources, voice capability, and personal context into a single cohesive assistant — built with clean architecture and production engineering standards from day one.

---

## 1. Project Vision

Most "AI assistant" projects are thin wrappers around a single LLM API call. NOVA is different by design:

- **Provider-agnostic intelligence** — NOVA can reason using Google Gemini, Groq, OpenRouter, or Cerebras, chosen dynamically based on cost, latency, capability, or availability, rather than being locked to one vendor.
- **Context-aware, not stateless** — NOVA is built to understand ongoing context (weather, news, location, search results) rather than answering in a vacuum.
- **Voice-capable** — through ElevenLabs integration, NOVA is designed to speak, not just print text.
- **Production-first** — every file follows real software engineering discipline: typed, logged, tested, documented, and secret-free. NOVA is meant to run reliably, not just demo well.
- **Long-term and modular** — NOVA is built incrementally, one well-defined module at a time, so the system remains maintainable as it grows from a simple assistant into a full personal companion platform.

---

## Core Philosophy

NOVA should feel like talking to a real companion rather than a chatbot.

Every response should be:

- Helpful
- Human-like
- Context aware
- Short unless detail is requested
- Emotionally intelligent
- Fast
- Honest
- Privacy first
- Modular

## 2. Features

### Current (Foundational Phase)
- Modular project architecture supporting multiple AI providers
- Environment-based secret and configuration management
- Clean separation between core logic, providers, and integrations

### Future
- Multi-provider AI routing with fallback logic (Gemini → Groq → OpenRouter → Cerebras)
- Real-time web search grounding via Tavily
- Voice input/output via ElevenLabs
- Location-aware responses via Google Maps
- Weather-aware context via OpenWeather
- News-aware context via NewsAPI
- Secure user authentication via Google OAuth
- Persistent memory and personalization
- Task automation and proactive companion behaviors
- Multi-modal input (text, voice, and beyond)
• Emotion Detection
• Automatic AI Model Switching
• Memory Engine
• Personality Engine
• Wake Word ("Hey Nova")
• Vision (Image Understanding)
• File Understanding
• Mac Control
• Browser Automation
• Plugin System
• Tool Calling
• Voice Interruptions
• Streaming Responses
• Offline Mode
• Self Healing Diagnostics
• Auto Update
• Skills Marketplace
• Learning User Habits

---

## 3. Architecture Overview

NOVA follows a **layered, clean architecture** approach:

```
┌─────────────────────────────┐
│        Interface Layer      │  (CLI / API / future UI)
├─────────────────────────────┤
│      Core Companion Logic   │  (orchestration, decision-making)
├─────────────────────────────┤
│   AI Provider Abstraction   │  (Gemini, Groq, OpenRouter, Cerebras)
├─────────────────────────────┤
│  Integration Services Layer │  (Tavily, ElevenLabs, Maps, Weather,
│                              │   News, OAuth)
├─────────────────────────────┤
│   Configuration & Secrets   │  (env-based settings, no hardcoding)
└─────────────────────────────┘
```

**Key principles:**
- Each AI provider and integration is wrapped behind a common interface, so swapping or adding providers never requires touching core logic.
- Configuration is centralized and environment-driven — no module reads secrets directly from disk or hardcodes them.
- Every layer is independently testable and independently replaceable.

---

## 4. Folder Structure

> This structure will be built incrementally, one file at a time, as the project progresses. It is documented here as the target layout.

```
nova/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── nova/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── companion.py
│   │   └── orchestrator.py
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   ├── openrouter_provider.py
│   │   └── cerebras_provider.py
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── tavily_search.py
│   │   ├── elevenlabs_voice.py
│   │   ├── openweather.py
│   │   ├── newsapi.py
│   │   ├── google_maps.py
│   │   └── google_oauth.py
│   │
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── cli.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py
│
└── tests/
    ├── __init__.py
    ├── test_providers/
    └── test_integrations/
```

---

## 5. AI Providers

NOVA integrates with multiple AI providers to avoid vendor lock-in and enable dynamic routing:

| Provider     | Role                                      |
|--------------|--------------------------------------------|
| Google Gemini | Primary reasoning / general-purpose AI    |
| Groq          | High-speed, low-latency inference          |
| OpenRouter    | Access to a broad range of model options   |
| Cerebras      | High-throughput inference workloads        |

---

## 6. APIs Used

| Service        | Purpose                                 |
|----------------|-------------------------------------------|
| Tavily Search  | Real-time web search grounding            |
| ElevenLabs     | Text-to-speech / voice generation          |
| OpenWeather    | Weather-aware context                      |
| NewsAPI        | News-aware context                         |
| Google Maps    | Location and mapping context               |
| Google OAuth   | Secure user authentication                 |

---

## 7. Installation

> Setup instructions will expand as core files are added. Baseline steps:

```bash
# Clone the repository
git clone https://github.com/your-org/nova.git
cd nova

# Create and activate a virtual environment
python3.14 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies (once requirements/pyproject are defined)
pip install -e .

# Copy environment template and fill in your own credentials
cp .env.example .env
```

---

## 8. Environment Variables

NOVA never hardcodes secrets. All credentials and configuration are supplied via environment variables (typically through a `.env` file, loaded at runtime).

```env
# AI Providers
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
CEREBRAS_API_KEY=

# Integrations
TAVILY_API_KEY=
ELEVENLABS_API_KEY=
OPENWEATHER_API_KEY=
NEWSAPI_KEY=
GOOGLE_MAPS_API_KEY=

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=

# App Settings
NOVA_ENV=development
LOG_LEVEL=INFO
```

> `.env` files must never be committed to version control. Use `.env.example` as the template with empty/placeholder values only.

---

## 9. Development Roadmap

| Phase | Focus |
|-------|-------|
| **Phase 1** | Project foundation — README, config/settings management, logging setup |
| **Phase 2** | AI provider abstraction layer (base interface + Gemini integration) |
| **Phase 3** | Additional AI providers (Groq, OpenRouter, Cerebras) with routing/fallback logic |
| **Phase 4** | Core companion orchestration logic |
| **Phase 5** | Web search grounding via Tavily |
| **Phase 6** | Voice output via ElevenLabs |
| **Phase 7** | Contextual integrations — OpenWeather, NewsAPI, Google Maps |
| **Phase 8** | Authentication via Google OAuth |
| **Phase 9** | Persistent memory, personalization, and user profiles |
| **Phase 10** | Advanced companion behaviors — proactive assistance, automation, multi-modal input |

---

## 10. Coding Standards

NOVA maintains strict engineering discipline across every file:

- **Python 3.14**, fully type-hinted
- **Docstrings** on all public modules, classes, and functions
- **Logging** instead of print statements, using the standard `logging` module
- **Explicit error handling** — no silent failures, no bare `except:`
- **Single Responsibility Principle** — one purpose per file/module
- **No hardcoded secrets** — configuration only via environment variables
- **One file generated/reviewed at a time** — no bundled or unreviewed changes
- Consistent formatting (PEP 8 compliant); linting/formatting tooling to be added in a later phase

---

## 11. Contribution Guidelines

Until NOVA reaches a stable public phase, contributions follow a strict process to preserve architectural integrity:

1. Discuss the proposed file or change before writing any code — explain **why**, **where**, and **how it connects**.
2. One file per change/commit — no multi-file bundles.
3. Do not modify existing files unless explicitly required and agreed upon.
4. All new code must include type hints, docstrings, logging, and proper error handling.
5. No secrets, credentials, or API keys committed to the repository.
6. New dependencies or integrations must be proposed and explained before being introduced.

---

## 12. License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2026 NOVA Project Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

---

## 13. Future Ideas

Ideas beyond the current 10-phase roadmap, to be evaluated as NOVA matures:

- Mobile companion app (iOS/Android) connecting to the NOVA backend
- Local/offline model support for privacy-sensitive use cases
- Plugin system for third-party integrations
- Calendar and email integration for proactive task management
- Emotion/tone-aware voice responses
- Multi-user household mode with per-user personalization
- Smart home integration (lights, thermostats, routines)
- Long-term memory with user-controlled data retention and export
- Self-hosted deployment option for full data ownership

---

*NOVA is under active, incremental development. This README will evolve alongside the project as new files and phases are added.*
