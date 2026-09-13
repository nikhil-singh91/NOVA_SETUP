# 10 — NOVA Environment Awareness & Pronoun Resolution

## Overview
NOVA maintains real-time perception of the user's computing context through `EnvironmentObserver` (EYES) and deterministically resolves ambiguous natural language references ("this", "that", "it", "here") through `ContextResolver`.

---

## 👁️ Observed Environment State (`EnvironmentContext`)
`EnvironmentObserver.refresh()` queries macOS via lightweight AppleScript calls (cached with 0.5s TTL) to capture:
- **Active Frontmost Application:** e.g. `"Google Chrome"`, `"Visual Studio Code"`, `"Finder"`, `"Terminal"`.
- **Active Window Title:** Exact title string of the front window.
- **Active Browser State:** Active tab index, tab count, current URL, domain, and page title.
- **Finder & Filesystem State:** Selected file/folder paths, open directory in active Finder window.
- **System Media & Recording:** Active screen recording status and output file path.

---

## 🔍 Deterministic Reference Resolution (`ContextResolver`)

When the user says:
- *"Delete **this**"* $\to$ Resolves to currently selected file/folder in Finder, or `last_created_path`.
- *"Search inside **this tab** for pricing"* $\to$ Resolves to active browser URL / tab.
- *"Open **that** in VS Code"* $\to$ Resolves to `last_created_path` or selected Finder file.
- *"What is **here**?"* $\to$ Resolves to current directory or visual cursor position.

```python
# Context resolution signature
resolved = ContextResolver.resolve_target(
    reference_term="this",
    context=environment_context,
    target_type="any" # "file", "url", "app", "any"
)
# Returns: {"resolved": True, "target": Path("/Users/.../file.py"), "target_type": "file"}
```
