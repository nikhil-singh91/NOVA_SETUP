# 25 — NOVA Known Limitations & System Constraints

## Overview
This document records verified hardware, OS, and software limitations present in the current NOVA codebase.

---

## ⚠️ Known Limitations & Operational Constraints

1. **Bluetooth Power Toggling:**
   - Querying Bluetooth status is natively supported via system commands.
   - Programmatically toggling Bluetooth power (`on`/`off`) on macOS requires the optional CLI utility `blueutil` (`brew install blueutil`). If absent, a warning is returned.

2. **AppleScript Browser Automation Headless Mode:**
   - `MacOSNativeBrowserEngine` controls real user browser windows in Chrome and Safari. It is intentionally not a headless Chromium browser; the user will see tab operations on screen.

3. **Screen OCR Language Support:**
   - Apple Vision framework OCR (`VNRecognizeTextRequest`) is optimized for Latin, Cyrillic, and select Asian character sets. Complex script parsing may require higher resolution or visual framing.

4. **Multi-Monitor Coordinate Offsets:**
   - Quartz mouse coordinates assume primary display origin `(0, 0)`. Secondary external monitors with virtual display offsets require active window bounds mapping.

5. **Local ASR Model Execution:**
   - Faster-Whisper defaults to `small.en` or `base` for low-latency CPU/Metal execution. Larger models (`large-v3`) require additional RAM and GPU compute.
