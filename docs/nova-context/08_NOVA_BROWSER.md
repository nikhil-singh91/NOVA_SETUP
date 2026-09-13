# 08 — NOVA Browser Automation & Web Skills

## Overview
NOVA provides native browser automation on macOS without requiring third-party browser extensions or intrusive debugging proxies. Automation is executed primarily through `MacOSNativeBrowserEngine` via AppleScript, interacting with Google Chrome and Safari.

---

## 🌐 Supported Web Skills & Integrations

### 1. YouTube & Media Playback (`browser/sites/youtube.py`)
- **Direct Search & Play:** `play blinding lights on youtube`, `listen to lofi beats`.
- **Auto-Play & Next:** Automatically selects the best search result and starts video playback.
- **YouTube Shorts Auto-Scroller (`browser/auto_scroll.py`):** Starts a background thread (`YouTubeShortsScroller`) that automatically scrolls through YouTube Shorts at configurable intervals (`browser_auto_shorts_interval_seconds = 15.0`).
- **Media Controls:** Supports pause, resume, scroll next, and volume adjustments.

### 2. Google Search (`browser/sites/google.py`)
- **Search Queries:** `search Google for quantum computing tutorials`.
- **Search Inside Current Tab:** `search within this tab for pricing`.
- **Snippet & Result Extraction:** Extracts top search titles, URLs, and snippets directly into context.

### 3. E-Commerce & Product Search (`browser/sites/amazon.py`)
- **Product Search:** `search Amazon for mechanical keyboards under $100`.
- **Filtering:** Filters by category, price, and customer rating.

### 4. Developer Search (`browser/sites/github.py`)
- **Repository Search:** `search GitHub for fast whisper macos`.
- **Direct Navigation:** Navigates directly to user/repository code trees.

### 5. Multi-Step Deep Web Research (`browser/planner.py`)
- **Autonomous Research Planner:** Decomposes a research question into multiple search queries, visits candidate pages, extracts text with `browser.extractor.WebpageExtractor`, and compiles a structured markdown summary report.

---

## 🛡️ Browser Safety Policy (`browser/safety.py`)
- **Dangerous Schemes Blocked:** `javascript:`, `data:`, `file:`, `vbscript:` URLs are automatically blocked.
- **Sensitive Operations Gate:** Financial transactions, password inputs, or account deletions trigger mandatory user confirmation prompts.
