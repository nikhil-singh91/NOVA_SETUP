"""NOVA Eyes: General-purpose real-time perception and interaction layer for macOS.

SEE -> UNDERSTAND -> PLAN -> ACT -> OBSERVE AGAIN -> VERIFY.
Pure in-memory, local-first, zero disk writes, zero cloud screen streaming.
"""

from __future__ import annotations

from core.eyes.accessibility import (
    AccessibilityInspector,
    SemanticElement,
    UIElementType,
)
from core.eyes.capture import DisplayMetrics, MemoryFrame, ScreenCapturer
from core.eyes.interaction import EyesInteractionManager
from core.eyes.manager import NovaEyesManager, nova_eyes
from core.eyes.planner import (
    ActionType,
    ConfidenceLevel,
    EyesTargetResolver,
)
from core.eyes.state import ScreenState
from core.eyes.verifier import EyesStateVerifier, VerificationOutcome
from core.eyes.vision_ocr import VisionOCR

__all__ = [
    "AccessibilityInspector",
    "ActionType",
    "ConfidenceLevel",
    "DisplayMetrics",
    "EyesInteractionManager",
    "EyesStateVerifier",
    "EyesTargetResolver",
    "MemoryFrame",
    "NovaEyesManager",
    "ScreenCapturer",
    "ScreenState",
    "SemanticElement",
    "UIElementType",
    "VerificationOutcome",
    "VisionOCR",
    "nova_eyes",
]
