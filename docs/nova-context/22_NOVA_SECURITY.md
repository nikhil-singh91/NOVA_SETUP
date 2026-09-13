# 22 — NOVA Security Architecture & Threat Model

## Overview
NOVA adheres to a strict local-first security architecture designed to prevent secret leaks, arbitrary command execution, unauthorized filesystem access, and rogue automation.

---

## 🔒 Security Tenets

### 1. Secret Isolation & Zero-Leak Logging
- **Configuration Encapsulation:** All API keys are loaded into Pydantic `SecretStr` containers.
- **Log Masking:** `log_environment_debug()` and `DashboardStatsManager` actively filter and redact key, token, auth, and password patterns before printing or storing log strings.
- **Repository Hygiene:** `.env` and `credentials.json` are excluded in `.gitignore`.

### 2. Guarded Execution & No Blind Shell Access
- **No Arbitrary Shell Invocation:** NOVA does not expose open `eval()` or unconstrained bash execution endpoints. Actions are strictly routed through validated capability handlers (`CapabilityRegistry`).
- **Confirmation for Irreversible Actions:** Deletion of files/directories and system power off/shutdown require explicit two-turn user confirmation.

### 3. Localhost IPC Binding
- **Loopback Enforcement:** The UI HTTP REST and WebSocket server binds strictly to `127.0.0.1:8765`, preventing inbound remote network access from the local area network.
- **CORS Restricted:** REST endpoints enforce strict origin headers.
