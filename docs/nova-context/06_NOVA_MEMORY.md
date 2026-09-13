# 06 — NOVA Memory Architecture & Persistence

## Overview
NOVA features a dual-layer memory system:
1. **Durable Structured Memory (`MemoryManager`):** Atomic JSON-persisted facts, user preferences, project tracking, goals, and session breadcrumbs stored at `data/memory/memory_store.json`.
2. **Semantic Vector Store (`VectorStore`):** Embedding-based document storage and semantic similarity search using ChromaDB (with pure in-memory fallback).

---

## 🗃️ Memory Categories (`MemoryCategory`)
- `PROFILE`: User identity, background, and personal facts.
- `PREFERENCES`: User settings, favorite tools, coding conventions, tone preferences.
- `PROJECTS`: Active codebase names, repository locations, project summaries.
- `CODING`: Coding patterns, architectural decisions, language preferences.
- `EDUCATION`: Learning goals, study topics, problem-solving history.
- `TASKS`: Actionable to-do items and multi-step task goals.
- `REMINDERS`: Time-based or event-based reminders.
- `CONVERSATIONS`: Important conversational summaries and facts.
- `NOTES`: Freeform notes.
- `GOALS`: Long-term objectives.
- `AI_SETTINGS`: Custom NOVA instructions and behavior overrides.

---

## 🔒 Atomic Persistence & Quarantine Guard
- **Atomic Writes:** Saves are executed by writing to a temporary file in the same filesystem directory followed by an atomic replace (`os.replace`), eliminating the risk of partial corruption during crashes.
- **Corrupted Store Quarantine:** If `memory_store.json` contains invalid JSON on startup, NOVA automatically renames it to `memory_store.json.corrupt.<timestamp>` and initializes a clean store rather than crashing.
- **Cross-Session Breadcrumbs:** On shutdown, `NovaApplication` writes a session breadcrumb summary (`_BREADCRUMB_KEY = "last_session_summary"`), allowing NOVA to greet the user with full context on subsequent startups.
