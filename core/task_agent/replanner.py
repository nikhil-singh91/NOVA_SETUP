"""Dynamic replanning engine handling step failures and bounded recovery in NOVA Task Agent V3."""

from __future__ import annotations

import time
from typing import Any

from core.logger import get_logger
from core.task_agent.models import (
    FailureType,
    StepStatus,
    TaskContext,
    TaskGoal,
    TaskPlan,
    TaskStep,
)
from core.task_agent.registry import CapabilityRegistry, capability_registry

logger = get_logger(__name__)


class DynamicReplanner:
    """Classifies execution failures and creates bounded replacement sub-plans."""

    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or capability_registry

    @classmethod
    def classify_failure(cls, error_msg: str | None, exc: Exception | None = None) -> FailureType:
        """Categorize failure into deterministic failure types."""
        if not error_msg and not exc:
            return FailureType.TRANSIENT

        full_str = f"{error_msg or ''} {str(exc) if exc else ''}".lower()

        if "cancel" in full_str or "stop" in full_str:
            return FailureType.CANCELLED

        if "permission" in full_str or "denied" in full_str or "unauthorized" in full_str:
            return FailureType.PERMISSION

        if "not found" in full_str or "missing" in full_str or "no such" in full_str or "cannot find" in full_str:
            return FailureType.NOT_FOUND

        if "ambiguous" in full_str or "multiple" in full_str or "clarif" in full_str:
            return FailureType.AMBIGUOUS

        if "timeout" in full_str or "temporary" in full_str or "stale" in full_str or "busy" in full_str:
            return FailureType.TRANSIENT

        return FailureType.TRANSIENT

    def can_retry_step(self, step: TaskStep, failure_type: FailureType) -> bool:
        """Determine if a failed step is eligible for an immediate retry."""
        if failure_type in (FailureType.CANCELLED, FailureType.PERMISSION, FailureType.UNSUPPORTED):
            return False
        return step.retry_count < step.max_retries

    def replan_failed_step(
        self,
        plan: TaskPlan,
        failed_step: TaskStep,
        failure_type: FailureType,
        ctx: TaskContext,
    ) -> list[TaskStep] | None:
        """Construct alternative replacement steps without resetting completed work."""
        logger.info(
            "Replanning failed step '%s' (cap='%s', failure_type=%s)",
            failed_step.step_id,
            failed_step.capability_name,
            failure_type.value,
        )

        # 1. Fallback: If visual click failed on website search, fallback to structured browser search
        if failed_step.capability_name == "visual.click_element":
            target_lbl = failed_step.parameters.get("target_label", "").lower()
            if "search" in target_lbl and ctx.active_urls:
                sub_step = TaskStep(
                    step_id=f"{failed_step.step_id}_fallback_search",
                    description=f"Fallback to structured browser site search for '{target_lbl}'",
                    capability_name="browser.search_web",
                    parameters={"query": target_lbl},
                )
                return [sub_step]

        # 2. Fallback: If folder creation on specific path failed, fallback to Desktop
        if failed_step.capability_name == "fs.create_folder" and failure_type == FailureType.NOT_FOUND:
            folder_name = failed_step.parameters.get("name", "Folder")
            fallback_step = TaskStep(
                step_id=f"{failed_step.step_id}_desktop_fallback",
                description=f"Fallback to creating '{folder_name}' directly on ~/Desktop",
                capability_name="fs.create_folder",
                parameters={"name": folder_name, "on_desktop": True},
            )
            return [fallback_step]

        return None
