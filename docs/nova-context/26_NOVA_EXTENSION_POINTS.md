# 26 — NOVA Extension Points & Developer Guide

## Overview
NOVA is designed to be easily extensible without modifying core orchestration loops or breaking existing test suites.

---

## 🔌 Preferred Extension Points

### 1. Registering New System Capabilities
New tools should be registered directly in `CapabilityRegistry` (`core.task_agent.registry`):

```python
from core.task_agent.models import RiskLevel, TaskContext
from core.task_agent.registry import CapabilityDefinition, capability_registry

def _my_custom_handler(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
    # Implementation logic
    return {"success": True, "result": "done"}

def _my_custom_verifier(params: dict[str, Any], result: dict[str, Any], ctx: TaskContext) -> bool:
    # Postcondition verification check
    return result.get("success", False)

capability_registry.register(
    CapabilityDefinition(
        name="custom.my_tool",
        subsystem="custom_tools",
        description="Description of what this tool accomplishes.",
        risk_level=RiskLevel.LOW,
        handler=_my_custom_handler,
        verifier=_my_custom_verifier,
        requires_confirmation=False,
    )
)
```

### 2. Adding New AI Providers
Subclass `providers.base_provider.BaseProvider`, implement `_generate_response_impl()`, `_stream_response_impl()`, and `health_check()`, then register with `ProviderManager`.

### 3. Adding New Web Site Skills
Add a new site skill class subclassing `browser.sites.base.BaseSiteSkill` inside `browser/sites/` and register it in `browser.router.BrowserActionRouter`.

### 4. Custom System Prompt Profiles
Register new prompt profiles with `SystemPromptManager` (`personality/system_prompt.py`) with specialized section templates and focus instructions.
