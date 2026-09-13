# 05 — NOVA Multi-Provider AI Architecture

## Overview
NOVA's AI brain is managed by `providers.provider_manager.ProviderManager`, a resilient multi-model orchestrator that isolates provider mechanics behind `providers.base_provider.BaseProvider`.

---

## 🔄 AI Request Flow
```
User Text / Turn Request
         │
         ▼
System Prompt & Personality Construction (`SystemPromptManager` + `EmotionEngine`)
         │
         ▼
`ProviderManager.generate_response(prompt, system_prompt, task_type)`
         │
    ┌────┴────────────────────────┐
    │ Task Routing Optimization   │
    ├─────────────────────────────┤
    │ CODING    -> Gemini -> Groq │
    │ REASONING -> Gemini -> OpenR│
    │ FAST      -> Groq   -> Cere │
    │ CHEAP     -> Cere   -> Groq │
    └────┬────────────────────────┘
         │
         ▼
Execute Request on Candidate Provider
    ├──> Success: Return response, update latency & token metrics
    └──> AIProviderError: Record error, switch instantly to next provider in priority list
         │
         ▼
Sanitization via `core.response_cleaner.clean_model_response`
         │
         ▼
Response Orchestration (`ResponseOrchestrator` -> TTS + UI)
```

---

## 🛡️ Provider Resiliency Features
1. **Zero-Crash Failover:** If an API endpoint experiences HTTP 429 (Rate Limit), 503 (Service Unavailable), or timeout, `ProviderManager` catches `AIProviderError` and invokes the fallback candidate automatically.
2. **Provider Health Monitoring:** Tracks per-provider consecutive failure counts, average latency, and last success timestamps.
3. **Manual Override Support:** Supports interactive debugging overrides (e.g. `/provider groq` or `/provider cerebras`).
4. **Token Budgeting:** Dynamically tunes `max_tokens` for voice turns (e.g. 120 tokens for greetings, 250 for quick answers, 500 for coding/reasoning) to minimize audio synthesis delay.
