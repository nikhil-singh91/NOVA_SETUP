# 03 — NOVA API Integrations & External Clients

## Overview
NOVA integrates with multiple external cloud AI services, web data providers, and native OS SDKs. All keys are loaded securely via `config.settings.settings` and validated at startup.

---

## ☁️ Cloud AI & Service Providers

### 1. Google Gemini
- **SDK:** `google-genai>=1.2.0` (`google.genai.Client`)
- **Config Key:** `GEMINI_API_KEY`
- **Default Model:** `gemini-2.5-flash`
- **Endpoints:** `generativelanguage.googleapis.com:443`
- **Capabilities:** High-speed streaming, structured JSON output, vision/multimodal reasoning, tool calling.
- **Failover Role:** Primary reasoning & coding provider in NOVA.

### 2. Groq
- **SDK:** `groq>=0.11.0` (`groq.Groq`)
- **Config Key:** `GROQ_API_KEY`
- **Default Model:** `groq/compound-mini` (or Llama 3 models)
- **Endpoints:** `api.groq.com:443`
- **Capabilities:** Ultra-low latency inference for quick conversational turns and fast mode tasks.
- **Failover Role:** Secondary fast provider.

### 3. OpenRouter
- **SDK:** `openai>=1.50.0` (`openai.OpenAI(base_url="https://openrouter.ai/api/v1")`)
- **Config Key:** `OPENROUTER_API_KEY`
- **Default Model:** `openai/gpt-4o-mini`
- **Endpoints:** `openrouter.ai:443`
- **Capabilities:** Broad multi-model access and backup reasoning.
- **Failover Role:** Secondary reasoning provider.

### 4. Cerebras Cloud
- **SDK:** `cerebras-cloud-sdk>=1.0.0` (`cerebras.cloud.sdk.Cerebras`)
- **Config Key:** `CEREBRAS_API_KEY`
- **Default Model:** `qwen-3.8-27b`
- **Endpoints:** `api.cerebras.ai:443`
- **Capabilities:** High-throughput low-cost inference.
- **Failover Role:** Primary cheap mode provider.

### 5. Web Search & Data Providers
- **Tavily:** `TAVILY_API_KEY` — Deep web search API for web research planner.
- **ElevenLabs:** `ELEVENLABS_API_KEY` — Optional high-fidelity neural voice synthesis.
- **OpenWeatherMap:** `OPENWEATHER_API_KEY` — Real-time weather diagnostics.
- **NewsAPI:** `NEWS_API_KEY` — Current news and media retrieval.
- **Google Maps:** `GOOGLE_MAPS_API_KEY` (Optional) — Location and navigation services.

---

## 🖥️ Native macOS System Bridges
- **AppleScript (`osascript`):** Used for Chrome/Safari browser tab manipulation, Finder queries, and system automation.
- **Quartz CoreGraphics (`pyobjc`):** In-memory Retina display capture (`CGWindowListCreateImage`) and hardware mouse/keyboard event injection (`CGEvent`).
- **Apple Vision Framework:** Native macOS OCR (`VNRecognizeTextRequest`) running on Apple Silicon Neural Engine.
- **PortAudio (`PyAudio`):** Low-latency 16kHz microphone stream capture.
