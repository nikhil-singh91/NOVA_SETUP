"""Automated diagnostic engine to check system health, providers, and environment."""

from __future__ import annotations

import os
import sys
import time
import socket
import threading
from pathlib import Path
from typing import Any, Callable
from collections import deque
from dataclasses import dataclass
import subprocess

from config.settings import settings
from core.registry import registry
from core.lifecycle import lifecycle


@dataclass
class LogEntry:
    """Represents a structured runtime log message for terminal and UI consoles."""

    timestamp: float
    level: str
    message: str
    logger_name: str = ""
    time_str: str = ""

    def __post_init__(self) -> None:
        if not self.time_str:
            self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))

    # Support backwards-compatible 2-tuple unpacking (lvl, msg = entry)
    def __iter__(self):
        yield self.level
        yield self.message

    def __getitem__(self, index: int) -> str:
        if index == 0:
            return self.level
        elif index == 1:
            return self.message
        raise IndexError("LogEntry index out of range")

    def __len__(self) -> int:
        return 2

    def formatted_line(self) -> str:
        return f"[{self.time_str}] [{self.level}] {self.message}"


@dataclass
class ActivityStep:
    """Represents an atomic interaction event in the user-facing activity feed."""

    category: str  # "YOU" | "UNDERSTOOD" | "ACTION" | "NOVA" | "RESULT" | "ERROR" | "SYSTEM"
    text: str
    timestamp: float
    time_str: str = ""
    details: dict[str, Any] = None  # type: ignore
    success: bool | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}
        if not self.time_str:
            self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))


@dataclass
class ActivityInteraction:
    """Groups a complete user turn (You -> Understood -> Action -> Nova -> Result) into a session block."""

    interaction_id: str
    timestamp: float
    time_str: str = ""
    user_query: str = ""
    raw_heard: str = ""
    verified_state: str = ""
    understood_intent: str = ""
    understood_details: dict[str, Any] = None  # type: ignore
    actions: list[str] = None  # type: ignore
    nova_response: str = ""
    result_message: str = ""
    result_success: bool | None = None
    steps: list[ActivityStep] = None  # type: ignore
    status: str = "IN_PROGRESS"  # "IN_PROGRESS" | "COMPLETED" | "FAILED"

    def __post_init__(self) -> None:
        if self.understood_details is None:
            self.understood_details = {}
        if self.actions is None:
            self.actions = []
        if self.steps is None:
            self.steps = []
        if not self.time_str:
            self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))


@dataclass
class SystemAlert:
    """Represents an active or resolved diagnostic system alert."""

    alert_id: str
    subsystem: str  # "PROVIDER" | "VOICE" | "MAC_CONTROL" | "BROWSER" | "MEMORY" | "NETWORK" | "SYSTEM"
    severity: str   # "WARNING" | "ERROR" | "CRITICAL"
    title: str      # e.g. "Gemini quota exceeded"
    details: str    # e.g. "Rate limited: You exceeded your current quota"
    timestamp: float
    time_str: str = ""
    recovery_hint: str = ""  # e.g. "Fallback provider active"
    retry_after: float | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.time_str:
            self.time_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))


class DashboardStatsManager:
    """Thread-safe state repository and diagnostic telemetry coordinator."""

    _lock = threading.Lock()
    _logs: deque[LogEntry] = deque(maxlen=3000)
    _log_callbacks: list[Callable[[LogEntry], None]] = []

    # Live Activity Feed Tracking
    _interactions: deque[ActivityInteraction] = deque(maxlen=500)
    _all_steps: deque[ActivityStep] = deque(maxlen=2000)
    _current_interaction: ActivityInteraction | None = None
    _activity_callbacks: list[Callable[[ActivityStep, ActivityInteraction], None]] = []

    # Real-Time System Recovery Alerts Engine
    _active_alerts: dict[str, SystemAlert] = {}
    _resolved_alerts: deque[SystemAlert] = deque(maxlen=20)

    # Real-Time Provider & Mac Action Telemetry
    _provider_live_stats: dict[str, dict[str, Any]] = {
        "gemini": {"status": "UNKNOWN", "latency": "N/A", "latency_ms": None, "last_request": "Never", "last_success": "Never", "last_error": None, "retry_after": None},
        "groq": {"status": "UNKNOWN", "latency": "N/A", "latency_ms": None, "last_request": "Never", "last_success": "Never", "last_error": None, "retry_after": None},
        "openrouter": {"status": "UNKNOWN", "latency": "N/A", "latency_ms": None, "last_request": "Never", "last_success": "Never", "last_error": None, "retry_after": None},
        "cerebras": {"status": "UNKNOWN", "latency": "N/A", "latency_ms": None, "last_request": "Never", "last_success": "Never", "last_error": None, "retry_after": None},
    }
    _recent_mac_actions: deque[dict[str, Any]] = deque(maxlen=5)

    _stats = {
        "voice_state": "BOOTING",
        "current_task": "System startup",
        "last_command": "None",
        "latency": "0.0s",
        "tokens": "0",
        "errors_count": 0,
        "warnings_count": 0,
        "last_error_module": "",
        "last_error_reason": "",
        "last_error_recovery": "",
        "active_provider": "Gemini",
        "fallback_active": False,
        "fallback_provider": "",
        "primary_failed_provider": "",
        "active_model": "gemini-2.5-flash",
        "temperature": "0.7",
        "network_status": "Healthy",
        "session_start_time": time.time(),
        "speech_confidence": "UNKNOWN",
        "estimated_snr": "0.0 dB",
        "mic_gain": "1.00x",
        "current_audio_state": "No Speech Detected",
        "whisper_confidence": "N/A",
        "intent_confidence": "0%",
        "recognition_latency": "0.00s",
        "rejection_reason": "None",
        "mic_state": "STANDBY",
        "recorder_state": "STOPPED",
        "thread_health": "HEALTHY",
        "recovery_count": 0,
        "whisper_state": "IDLE",
        "model_loaded": "No",
        "model_memory": "None",
        "rms": "0.0000",
        "noise_floor": "0.0000",
        "overall_confidence": "0%",
        "queue_size": "0 chunks",
        "last_exception": "None",
        "mac_control_status": "Checking...",
        "mac_intent": "None",
        "mac_target": "None",
        "mac_latency": "N/A",
        "mac_result": "None"
    }

    # -------------------------------------------------------------------------
    # System Recovery Alerts API
    # -------------------------------------------------------------------------

    @classmethod
    def raise_alert(
        cls,
        alert_id: str,
        subsystem: str,
        severity: str,
        title: str,
        details: str,
        recovery_hint: str = "",
        retry_after: float | None = None,
    ) -> None:
        """Raise or update an active real-time diagnostic system alert."""
        ts = time.time()
        alert = SystemAlert(
            alert_id=alert_id,
            subsystem=subsystem,
            severity=severity,
            title=title,
            details=details,
            timestamp=ts,
            recovery_hint=recovery_hint,
            retry_after=retry_after,
            is_active=True,
        )
        with cls._lock:
            cls._active_alerts[alert_id] = alert
            cls._stats["errors_count"] = len(cls._active_alerts)
            cls._stats["last_error_module"] = subsystem
            cls._stats["last_error_reason"] = title
            cls._stats["last_error_recovery"] = recovery_hint
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(ActivityStep(category="ERROR", text=f"{title}: {details}", timestamp=ts), None)
            except Exception:
                pass

    @classmethod
    def clear_alert(cls, alert_id: str, resolution_title: str = "") -> None:
        """Clear an active alert and record it in recent resolved events."""
        with cls._lock:
            alert = cls._active_alerts.pop(alert_id, None)
            if alert:
                alert.is_active = False
                if resolution_title:
                    alert.title = resolution_title
                cls._resolved_alerts.appendleft(alert)
                cls._stats["errors_count"] = len(cls._active_alerts)
                if not cls._active_alerts:
                    cls._stats["last_error_module"] = ""
                    cls._stats["last_error_reason"] = ""
                    cls._stats["last_error_recovery"] = ""

    @classmethod
    def get_active_alerts(cls) -> list[SystemAlert]:
        """Return list of all currently active system alerts."""
        with cls._lock:
            return list(cls._active_alerts.values())

    @classmethod
    def get_resolved_alerts(cls) -> list[SystemAlert]:
        """Return list of recently resolved events."""
        with cls._lock:
            return list(cls._resolved_alerts)

    # -------------------------------------------------------------------------
    # Real-Time Provider Telemetry API
    # -------------------------------------------------------------------------

    @classmethod
    def record_provider_success(
        cls,
        name: str,
        latency_ms: float,
        fallback_used: bool = False,
        primary_failed: str = "",
    ) -> None:
        """Record real-time successful provider execution."""
        name_lower = name.lower()
        now_str = time.strftime("%H:%M:%S")
        lat_str = f"{int(latency_ms)} ms" if latency_ms < 1000 else f"{latency_ms/1000:.2f} s"

        with cls._lock:
            if name_lower not in cls._provider_live_stats:
                cls._provider_live_stats[name_lower] = {}
            cls._provider_live_stats[name_lower].update({
                "status": "HEALTHY",
                "latency": lat_str,
                "latency_ms": latency_ms,
                "last_request": now_str,
                "last_success": now_str,
                "last_error": None,
                "retry_after": None,
            })
            cls._stats["active_provider"] = name.title()
            cls._stats["latency"] = lat_str
            if fallback_used:
                cls._stats["fallback_active"] = True
                cls._stats["fallback_provider"] = name.title()
                if primary_failed:
                    cls._stats["primary_failed_provider"] = primary_failed.title()
            else:
                cls._stats["fallback_active"] = False

        # Clear active alert for this provider if it recovered
        cls.clear_alert(f"provider_{name_lower}", resolution_title=f"{name.title()} recovered")

    @classmethod
    def record_provider_failure(
        cls,
        name: str,
        status: str,
        error_msg: str,
        latency_ms: float | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Record real-time provider failure with status classification and retry timer."""
        name_lower = name.lower()
        now_str = time.strftime("%H:%M:%S")
        lat_str = (f"{int(latency_ms)} ms" if latency_ms < 1000 else f"{latency_ms/1000:.2f} s") if latency_ms else "N/A"
        retry_str = f"{int(retry_after)}s" if retry_after else None

        with cls._lock:
            if name_lower not in cls._provider_live_stats:
                cls._provider_live_stats[name_lower] = {}
            cls._provider_live_stats[name_lower].update({
                "status": status,
                "latency": lat_str,
                "latency_ms": latency_ms,
                "last_request": now_str,
                "last_error": error_msg,
                "retry_after": retry_str,
            })

        # Raise recovery alert
        cls.raise_alert(
            alert_id=f"provider_{name_lower}",
            subsystem="PROVIDER",
            severity="WARNING" if "QUOTA" in status or "RATE" in status else "ERROR",
            title=f"{name.title()} {status.lower()}",
            details=error_msg,
            recovery_hint="Fallback provider activated" if status in ("QUOTA EXCEEDED", "RATE LIMITED", "RATE_LIMITED", "ERROR", "OFFLINE", "UNAVAILABLE", "AUTH_ERROR", "NETWORK_ERROR", "TIMEOUT") else "",
            retry_after=retry_after,
        )

    @classmethod
    def get_provider_stats(cls) -> dict[str, dict[str, Any]]:
        """Return snapshot of real-time provider statuses."""
        with cls._lock:
            return {k: dict(v) for k, v in cls._provider_live_stats.items()}

    # -------------------------------------------------------------------------
    # Real-Time Mac Action Telemetry API
    # -------------------------------------------------------------------------

    @classmethod
    def record_mac_action(
        cls,
        command_text: str,
        intent: str,
        target: str,
        status: str,
        latency_ms: float | None = None,
        result_message: str = "",
    ) -> None:
        """Record real-time Mac control execution details and append to recent actions."""
        now_str = time.strftime("%H:%M:%S")
        lat_str = f"{int(latency_ms)} ms" if latency_ms is not None and latency_ms < 1000 else (f"{latency_ms/1000:.2f} s" if latency_ms is not None else "N/A")
        
        action_item = {
            "time": now_str,
            "command": command_text,
            "intent": intent,
            "target": target,
            "status": status,
            "latency": lat_str,
            "result": result_message,
        }

        with cls._lock:
            cls._recent_mac_actions.appendleft(action_item)
            cls._stats["last_command"] = command_text
            cls._stats["mac_intent"] = intent
            cls._stats["mac_target"] = target
            cls._stats["command_status"] = status
            cls._stats["mac_latency"] = lat_str
            cls._stats["mac_result"] = result_message

        if status in ("FAILED", "PERMISSION_DENIED"):
            cls.raise_alert(
                alert_id=f"mac_action_{int(time.time()*1000)}",
                subsystem="MAC_CONTROL",
                severity="WARNING",
                title=f"Mac Action Failed: {command_text}",
                details=result_message or "Execution failed",
                recovery_hint="Check application name or system permissions",
            )

    @classmethod
    def get_recent_mac_actions(cls) -> list[dict[str, Any]]:
        """Return last 5 executed Mac actions."""
        with cls._lock:
            return list(cls._recent_mac_actions)

    @classmethod
    def check_mac_control_access(cls) -> str:
        """Check real macOS permissions (AppleScript / System Events)."""
        if sys.platform != "darwin":
            return "LIMITED (Non-macOS)"
        try:
            res = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of current user'],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode == 0:
                return "GRANTED"
            elif "not allowed" in res.stderr.lower() or "1743" in res.stderr:
                return "DENIED (Accessibility required)"
            return "LIMITED"
        except Exception:
            return "UNKNOWN"

    @classmethod
    def update(cls, key: str, value: Any) -> None:
        with cls._lock:
            cls._stats[key] = value

    @classmethod
    def get_eyes_status(cls) -> dict[str, Any]:
        """Fetch current real-time status and metrics from NOVA Eyes."""
        try:
            from core.eyes import nova_eyes
            return nova_eyes.get_status()
        except Exception:
            return {
                "status": "UNAVAILABLE",
                "capture_engine": "None",
                "semantic_engine": "None",
                "vision_engine": "None",
                "ocr_mode": "Local-first",
                "disk_storage": "OFF",
                "recording": "OFF",
                "cloud_streaming": "OFF",
            }

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        with cls._lock:
            return dict(cls._stats)

    @classmethod
    def report_error(cls, module: str, reason: str, recovery: str) -> None:
        with cls._lock:
            cls._stats["errors_count"] += 1
            cls._stats["last_error_module"] = module
            cls._stats["last_error_reason"] = reason
            cls._stats["last_error_recovery"] = recovery

    @classmethod
    def report_warning(cls, module: str, reason: str) -> None:
        with cls._lock:
            cls._stats["warnings_count"] += 1

    # -------------------------------------------------------------------------
    # Activity Feed Tracking Methods (YOU, UNDERSTOOD, ACTION, NOVA, RESULT)
    # -------------------------------------------------------------------------

    @classmethod
    def register_activity_callback(cls, callback: Callable[[ActivityStep, ActivityInteraction], None]) -> None:
        with cls._lock:
            if callback not in cls._activity_callbacks:
                cls._activity_callbacks.append(callback)

    @classmethod
    def unregister_activity_callback(cls, callback: Callable[[ActivityStep, ActivityInteraction], None]) -> None:
        with cls._lock:
            if callback in cls._activity_callbacks:
                cls._activity_callbacks.remove(callback)

    @classmethod
    def start_interaction(
        cls,
        user_text: str,
        source: str = "voice",
        timestamp: float | None = None,
        interaction_id: str | None = None,
    ) -> ActivityInteraction:
        """Start a new user interaction block in the activity feed."""
        ts = timestamp if timestamp is not None else time.time()
        iid = interaction_id or f"turn_{int(ts * 1000)}"

        interaction = ActivityInteraction(
            interaction_id=iid,
            timestamp=ts,
            user_query=user_text,
            status="IN_PROGRESS",
        )
        step = ActivityStep(
            category="YOU",
            text=user_text,
            timestamp=ts,
            details={"source": source},
        )
        interaction.steps.append(step)

        with cls._lock:
            cls._current_interaction = interaction
            cls._interactions.append(interaction)
            cls._all_steps.append(step)
            cls._stats["last_command"] = user_text
            cls._stats["current_task"] = f"Processing: {user_text[:30]}"
            cls._stats["mac_intent"] = "None"
            cls._stats["mac_target"] = "None"
            cls._stats["mac_result"] = "None"
            cls._stats["command_status"] = "IN_PROGRESS"
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, interaction)
            except Exception:
                pass

        return interaction

    @classmethod
    def record_heard(
        cls,
        raw_transcript: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record the exact raw ASR speech transcript as heard by Whisper."""
        ts = time.time()
        step = ActivityStep(
            category="HEARD",
            text=raw_transcript,
            timestamp=ts,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.raw_heard = raw_transcript
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    raw_heard=raw_transcript,
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            cls._stats["last_transcript"] = raw_transcript
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_understood(
        cls,
        intent: str,
        details: dict[str, Any] | None = None,
        summary: str = "",
    ) -> None:
        """Record what NOVA understood from the user's command."""
        ts = time.time()
        step = ActivityStep(
            category="UNDERSTOOD",
            text=intent,
            timestamp=ts,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.understood_intent = intent
                inter.understood_details = dict(details or {})
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    understood_intent=intent,
                    understood_details=dict(details or {}),
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            cls._stats["command_category"] = intent
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_resolve(
        cls,
        target: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record contextual reference resolution step."""
        ts = time.time()
        step = ActivityStep(
            category="RESOLVE",
            text=target,
            timestamp=ts,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_action(
        cls,
        action_text: str,
        step_num: int | None = None,
        total_steps: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an action step that NOVA is currently executing."""
        ts = time.time()
        act_details = dict(details or {})
        if step_num is not None:
            act_details["step_num"] = step_num
        if total_steps is not None:
            act_details["total_steps"] = total_steps

        step = ActivityStep(
            category="ACTION",
            text=action_text,
            timestamp=ts,
            details=act_details,
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.actions.append(action_text)
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    actions=[action_text],
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            cls._stats["current_task"] = f"Executing: {action_text}"
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_verify(
        cls,
        verify_text: str,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record system-level verification outcome."""
        ts = time.time()
        step = ActivityStep(
            category="VERIFY",
            text=verify_text,
            timestamp=ts,
            success=success,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.verified_state = verify_text
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    verified_state=verify_text,
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_nova(cls, response_text: str) -> None:
        """Record NOVA's spoken assistant response text."""
        ts = time.time()
        step = ActivityStep(
            category="NOVA",
            text=response_text,
            timestamp=ts,
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.nova_response = response_text
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    nova_response=response_text,
                    steps=[step],
                )
                cls._interactions.append(inter)
                cls._current_interaction = inter

            cls._all_steps.append(step)
            cls._stats["current_task"] = "Speaking..."
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_result(
        cls,
        result_text: str,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record the final outcome of the action or turn."""
        ts = time.time()
        step = ActivityStep(
            category="RESULT",
            text=result_text,
            timestamp=ts,
            success=success,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.result_message = result_text
                inter.result_success = success
                inter.status = "COMPLETED" if success else "FAILED"
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    result_message=result_text,
                    result_success=success,
                    status="COMPLETED" if success else "FAILED",
                    steps=[step],
                )
                cls._interactions.append(inter)

            cls._all_steps.append(step)
            cls._stats["command_status"] = "SUCCESS" if success else "FAILED"
            cls._stats["command_result"] = result_text
            cls._stats["current_task"] = "Idle"
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_error(cls, error_text: str, details: dict[str, Any] | None = None) -> None:
        """Record an error event in the activity feed."""
        ts = time.time()
        step = ActivityStep(
            category="ERROR",
            text=error_text,
            timestamp=ts,
            success=False,
            details=dict(details or {}),
        )

        with cls._lock:
            inter = cls._current_interaction
            if inter is not None:
                inter.result_message = error_text
                inter.result_success = False
                inter.status = "FAILED"
                inter.steps.append(step)
            else:
                inter = ActivityInteraction(
                    interaction_id=f"turn_{int(ts * 1000)}",
                    timestamp=ts,
                    result_message=error_text,
                    result_success=False,
                    status="FAILED",
                    steps=[step],
                )
                cls._interactions.append(inter)

            cls._all_steps.append(step)
            cls._stats["errors_count"] += 1
            cls._stats["last_error_reason"] = error_text
            cls._stats["current_task"] = "Error encountered"
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_system(cls, system_text: str) -> None:
        """Record an important user-relevant system event."""
        ts = time.time()
        step = ActivityStep(
            category="SYSTEM",
            text=system_text,
            timestamp=ts,
        )

        with cls._lock:
            cls._all_steps.append(step)
            inter = cls._current_interaction or ActivityInteraction(
                interaction_id=f"sys_{int(ts * 1000)}",
                timestamp=ts,
                steps=[step],
            )
            callbacks = list(cls._activity_callbacks)

        for cb in callbacks:
            try:
                cb(step, inter)
            except Exception:
                pass

    @classmethod
    def record_status(cls, status_text: str) -> None:
        """Record an activity status update."""
        cls.record_system(status_text)

    @classmethod
    def get_activity_interactions(
        cls,
        limit: int | None = None,
        filter_category: str | None = None,
        search_query: str | None = None,
    ) -> list[ActivityInteraction]:
        """Fetch filtered activity interaction blocks."""
        with cls._lock:
            items = list(cls._interactions)

        # Apply category filter if specified (e.g. "YOU", "UNDERSTOOD", "ACTION", "NOVA", "RESULT")
        if filter_category and filter_category.upper() not in ("ALL", "ACTIVITY"):
            cat_upper = filter_category.upper()
            filtered = []
            for inter in items:
                matching_steps = [s for s in inter.steps if s.category.upper() == cat_upper]
                if matching_steps:
                    filtered.append(inter)
            items = filtered

        # Apply text search query
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            filtered = []
            for inter in items:
                matches_user = q in inter.user_query.lower()
                matches_intent = q in inter.understood_intent.lower()
                matches_actions = any(q in a.lower() for a in inter.actions)
                matches_nova = q in inter.nova_response.lower()
                matches_result = q in inter.result_message.lower()
                matches_steps = any(q in s.text.lower() for s in inter.steps)
                if matches_user or matches_intent or matches_actions or matches_nova or matches_result or matches_steps:
                    filtered.append(inter)
            items = filtered

        if limit is not None and limit > 0:
            return items[-limit:]
        return items

    @classmethod
    def get_activity_steps(
        cls,
        limit: int | None = None,
        filter_category: str | None = None,
        search_query: str | None = None,
    ) -> list[ActivityStep]:
        """Fetch flat activity steps."""
        with cls._lock:
            items = list(cls._all_steps)

        if filter_category and filter_category.upper() not in ("ALL", "ACTIVITY"):
            cat_upper = filter_category.upper()
            items = [s for s in items if s.category.upper() == cat_upper]

        if search_query and search_query.strip():
            q = search_query.strip().lower()
            items = [s for s in items if q in s.text.lower() or any(q in str(v).lower() for v in s.details.values())]

        if limit is not None and limit > 0:
            return items[-limit:]
        return items

    @classmethod
    def clear_activities(cls) -> None:
        """Clear user activity feed history."""
        with cls._lock:
            cls._interactions.clear()
            cls._all_steps.clear()
            cls._current_interaction = None

    @classmethod
    def get_activity_as_text(cls) -> str:
        """Export formatted activity feed as readable text."""
        inters = cls.get_activity_interactions()
        lines: list[str] = []
        for inter in inters:
            lines.append("=" * 50)
            for step in inter.steps:
                lines.append(f"{step.time_str}  {step.category}")
                lines.append(f"  {step.text}")
                if step.details:
                    for k, v in step.details.items():
                        lines.append(f"  {k}: {v}")
                lines.append("")
        return "\n".join(lines)

    @classmethod
    def copy_activity_to_clipboard(cls) -> bool:
        """Copy formatted user activity feed to macOS clipboard."""
        text = cls.get_activity_as_text()
        if not text:
            return False
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, close_fds=True)
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Raw Log Handling (Kept for Debug Mode & Technical Tracebacks)
    # -------------------------------------------------------------------------

    @classmethod
    def register_log_callback(cls, callback: Callable[[LogEntry], None]) -> None:
        with cls._lock:
            if callback not in cls._log_callbacks:
                cls._log_callbacks.append(callback)

    @classmethod
    def unregister_log_callback(cls, callback: Callable[[LogEntry], None]) -> None:
        with cls._lock:
            if callback in cls._log_callbacks:
                cls._log_callbacks.remove(callback)

    @classmethod
    def add_log(
        cls,
        level: str,
        msg: str,
        timestamp: float | None = None,
        logger_name: str = ""
    ) -> None:
        # Normalize log levels
        lvl_upper = level.upper()
        if lvl_upper in ("WARNING", "WARN"):
            norm_level = "WARN"
        elif lvl_upper in ("ERROR", "CRITICAL"):
            norm_level = "ERROR"
        elif lvl_upper in ("SUCCESS", "OK"):
            norm_level = "SUCCESS"
        elif lvl_upper in ("DEBUG", "DBG"):
            norm_level = "DEBUG"
        else:
            norm_level = "INFO"

        entry = LogEntry(
            timestamp=timestamp if timestamp is not None else time.time(),
            level=norm_level,
            message=msg,
            logger_name=logger_name,
        )

        with cls._lock:
            cls._logs.append(entry)
            callbacks = list(cls._log_callbacks)

        for cb in callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    @classmethod
    def get_logs(
        cls,
        limit: int | None = None,
        level_filter: str | None = None,
        search_query: str | None = None,
    ) -> list[LogEntry]:
        with cls._lock:
            items = list(cls._logs)

        # Apply level filter if set and not "ALL"
        if level_filter and level_filter.upper() != "ALL":
            filter_norm = level_filter.upper()
            if filter_norm == "WARNING":
                filter_norm = "WARN"
            items = [item for item in items if item.level == filter_norm]

        # Apply text search query
        if search_query and search_query.strip():
            query_lower = search_query.strip().lower()
            items = [
                item for item in items
                if query_lower in item.message.lower() or query_lower in item.logger_name.lower()
            ]

        if limit is not None and limit > 0:
            return items[-limit:]
        return items

    @classmethod
    def clear_logs(cls) -> None:
        """Clear activity history, raw debug logs, recent mac actions, and alerts."""
        with cls._lock:
            cls._logs.clear()
            cls._interactions.clear()
            cls._all_steps.clear()
            cls._current_interaction = None
            cls._recent_mac_actions.clear()
            cls._active_alerts.clear()
            cls._resolved_alerts.clear()

    @classmethod
    def get_logs_as_text(
        cls,
        level_filter: str | None = None,
        search_query: str | None = None,
    ) -> str:
        """Export current log entries as plain newline-delimited text."""
        logs = cls.get_logs(level_filter=level_filter, search_query=search_query)
        return "\n".join(entry.formatted_line() for entry in logs)

    @classmethod
    def copy_to_clipboard(
        cls,
        level_filter: str | None = None,
        search_query: str | None = None,
    ) -> bool:
        """Copy formatted log entries directly to macOS system clipboard."""
        text = cls.get_logs_as_text(level_filter=level_filter, search_query=search_query)
        if not text:
            return False
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, close_fds=True)
            process.communicate(input=text.encode("utf-8"))
            return process.returncode == 0
        except Exception:
            return False


class HealthChecker:
    """Performs real runtime diagnostic tests across all NOVA subsystems."""

    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}
        self._init_placeholder_results()

    def _init_placeholder_results(self) -> None:
        import os
        model_name = (os.environ.get("WHISPER_MODEL_NAME") or settings.whisper_model_name or "small").capitalize()
        self.results = {
            "core": {
                "Lifecycle": {"status": "Healthy", "message": "Checking..."},
                "Registry": {"status": "Healthy", "message": "Checking..."},
                "Memory Manager": {"status": "Healthy", "message": "Checking..."},
                "Vector Store": {"status": "Healthy", "message": "Checking..."},
                "Prompt Manager": {"status": "Healthy", "message": "Checking..."},
                "Emotion Engine": {"status": "Healthy", "message": "Checking..."},
                "Provider Manager": {"status": "Healthy", "message": "Checking..."},
                "Speech Recognition": {"status": "Healthy", "message": "Checking..."},
                "Text To Speech": {"status": "Healthy", "message": "Checking..."},
                "macOS Control": {"status": "Healthy", "message": "Checking..."}
            },
            "voice": {
                "Speech Engine": f"Whisper (Local/{model_name})",
                "Voice Engine": f"Edge-TTS ({settings.tts_voice})",
                "Language": "Hindi / English",
                "Speech Rate": "1.0x",
                "Microphone": "Checking...",
                "Speaker": "Checking...",
                "Microphone Permission": "Checking...",
                "Speaker Permission": "Checking..."
            },
            "providers": {
                "Internet": {"status": "Checking...", "message": "Checking..."},
                "Gemini": {"status": "Checking...", "message": "Checking..."},
                "Groq": {"status": "Checking...", "message": "Checking..."},
                "OpenRouter": {"status": "Checking...", "message": "Checking..."},
                "Cerebras": {"status": "Checking...", "message": "Checking..."}
            },
            "memory": {
                "Memory Backend": "Local JSON store",
                "Semantic Search": "Checking...",
                "Stored Memories": "Checking...",
                "Memory File": "Checking...",
                "Vector Backend": "Checking...",
                "Memory Status": "Healthy"
            },
            "environment": {
                ".env status": "Checking...",
                "preferences.json": "Checking...",
                "working_dirs": "Checking..."
            },
            "performance": {
                "CPU": "Checking...",
                "RAM": "Checking...",
                "Threads": "0",
                "PID": 0,
                "Python Memory": "Checking..."
            }
        }

    def run_all_checks(self) -> dict[str, dict[str, Any]]:
        """Return currently cached diagnostic results without blocking."""
        return self.results

    def run_checks_async(self) -> None:
        """Trigger diagnostic checks in a separate daemon thread to avoid blocking startup."""
        def _check_task():
            try:
                core_res = self.check_core()
                self.results["core"] = core_res
            except Exception:
                pass
                
            try:
                voice_res = self.check_voice()
                self.results["voice"] = voice_res
            except Exception:
                pass
                
            try:
                prov_res = self.check_providers()
                self.results["providers"] = prov_res
            except Exception:
                pass
                
            try:
                mem_res = self.check_memory()
                self.results["memory"] = mem_res
            except Exception:
                pass
                
            try:
                env_res = self.check_environment()
                self.results["environment"] = env_res
            except Exception:
                pass
                
            try:
                perf_res = self.get_performance()
                self.results["performance"] = perf_res
            except Exception:
                pass

        threading.Thread(target=_check_task, daemon=True, name="nova-health-checker").start()

    def check_core(self) -> dict[str, Any]:
        """Verify core lifecycle services status and health."""
        checks = {}
        
        # 1. Lifecycle
        try:
            checks["Lifecycle"] = {
                "status": "Healthy" if lifecycle.is_running() else "Warning",
                "message": "Lifecycle active" if lifecycle.is_running() else "Not fully running"
            }
        except Exception as exc:
            checks["Lifecycle"] = {"status": "Failed", "message": str(exc)}

        # 2. Service Registry
        try:
            services_count = len(registry._services)
            checks["Registry"] = {
                "status": "Healthy" if services_count > 0 else "Warning",
                "message": f"{services_count} services active"
            }
        except Exception as exc:
            checks["Registry"] = {"status": "Failed", "message": str(exc)}

        # Map registry services to their health checks
        registered_managers = {
            "memory_manager": "Memory Manager",
            "vector_store": "Vector Store",
            "system_prompt_manager": "Prompt Manager",
            "emotion_engine": "Emotion Engine",
            "provider_manager": "Provider Manager",
            "stt_manager": "Speech Recognition",
            "tts_manager": "Text To Speech",
            "mac_control_manager": "macOS Control"
        }

        for registry_name, display_name in registered_managers.items():
            try:
                if registry.exists(registry_name):
                    manager = registry.get(registry_name)
                    # Check if manager has a health_check method
                    if hasattr(manager, "health_check"):
                        check_res = manager.health_check()
                        if isinstance(check_res, dict):
                            is_healthy = any(check_res.values())
                            active_cnt = sum(1 for v in check_res.values() if v)
                            msg = f"{active_cnt}/{len(check_res)} providers healthy"
                        else:
                            is_healthy = bool(check_res)
                            msg = "Initialized & healthy" if is_healthy else "Health check returned warning/failed"
                        checks[display_name] = {
                            "status": "Healthy" if is_healthy else "Warning",
                            "message": msg
                        }
                    else:
                        checks[display_name] = {
                            "status": "Healthy",
                            "message": "Active in registry"
                        }
                else:
                    checks[display_name] = {
                        "status": "Failed",
                        "message": "Not initialized or registered"
                    }
            except Exception as exc:
                checks[display_name] = {
                    "status": "Failed",
                    "message": str(exc)
                }

        return checks

    def check_voice(self) -> dict[str, Any]:
        """Inspect voice drivers, rate, default device configs, and microphone access."""
        import os
        model_name = (os.environ.get("WHISPER_MODEL_NAME") or settings.whisper_model_name or "small").capitalize()
        checks = {
            "Speech Engine": f"Whisper (Local/{model_name})",
            "Voice Engine": f"Edge-TTS ({settings.tts_voice})",
            "Language": "Hindi / English (Bilingual)",
            "Speech Rate": "1.0x",
            "Microphone": "Unavailable",
            "Speaker": "Unavailable",
            "Microphone Permission": "Unknown",
            "Speaker Permission": "Unknown"
        }

        # Query audio hardware via PyAudio
        p = None
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            
            # Find default input/output devices
            try:
                default_input = p.get_default_input_device_info()
                checks["Microphone"] = default_input.get("name", "Unknown Microphone")
            except IOError:
                checks["Microphone"] = "No default input device"

            try:
                default_output = p.get_default_output_device_info()
                checks["Speaker"] = default_output.get("name", "Unknown Speaker")
            except IOError:
                checks["Speaker"] = "No default output device"

            # Check Microphone Permission based on device detection
            if checks.get("Microphone") != "No default input device":
                checks["Microphone Permission"] = "Granted"
            else:
                checks["Microphone Permission"] = "Unavailable"

            # Check Speaker Permission based on device detection
            if checks.get("Speaker") != "No default output device":
                checks["Speaker Permission"] = "Granted"
            else:
                checks["Speaker Permission"] = "Unavailable"

            # Perform real validation on active microphone stream via stats snapshot
            try:
                from ui.health_checker import DashboardStatsManager
                mic_state = DashboardStatsManager.get_all().get("mic_state", "STANDBY")
                if mic_state == "ON":
                    checks["Microphone"] = f"{checks['Microphone']} (Active)"
                    checks["Microphone Permission"] = "Granted (Active)"
            except Exception:
                pass

            # Perform real validation on active speaker driver
            try:
                import pygame
                if pygame.mixer.get_init():
                    checks["Speaker"] = f"{checks['Speaker']} (Pygame Active)"
            except Exception:
                pass

        except Exception as exc:
            checks["Microphone"] = f"Failed to initialize pyaudio: {exc}"
            checks["Microphone Permission"] = "Failed"
            checks["Speaker Permission"] = "Failed"
        finally:
            if p is not None:
                try:
                    p.terminate()
                except Exception:
                    pass

        return checks

    def check_providers(self) -> dict[str, Any]:
        """Test API configuration and connectivity for AI providers."""
        checks = {}
        
        # Test internet connectivity
        internet_connected = False
        try:
            socket.setdefaulttimeout(1.5)
            # Query DNS to check connection
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            internet_connected = True
            checks["Internet"] = {"status": "Healthy", "message": "Connected"}
        except Exception:
            checks["Internet"] = {"status": "Warning", "message": "Offline / Port 53 Blocked"}

        # Query Provider Manager details
        provider_keys = {
            "gemini": ("Gemini", settings.gemini_api_key.get_secret_value()),
            "groq": ("Groq", settings.groq_api_key.get_secret_value()),
            "openrouter": ("OpenRouter", settings.openrouter_api_key.get_secret_value()),
            "cerebras": ("Cerebras", settings.cerebras_api_key.get_secret_value())
        }

        # Check configured states
        for key_name, (display_name, secret_val) in provider_keys.items():
            if not secret_val or not secret_val.strip() or secret_val.startswith("PASTE_"):
                checks[display_name] = {
                    "status": "UNAVAILABLE",
                    "message": "API key missing/unconfigured",
                    "latency": "N/A"
                }
                continue

            # Retrieve real runtime state from DashboardStatsManager
            live_stats = DashboardStatsManager.get_provider_stats().get(key_name, {})
            rt_status = live_stats.get("status", "UNKNOWN")
            latency_str = live_stats.get("latency", "N/A")
            last_err = live_stats.get("last_error")
            retry_after = live_stats.get("retry_after")

            if rt_status != "UNKNOWN":
                status_level = rt_status
                status_desc = last_err or ("Connected" if rt_status == "HEALTHY" else rt_status)
                if retry_after:
                    status_desc += f" (Retry: {retry_after})"
            else:
                # Initial check if no runtime request has occurred yet
                if registry.exists("provider_manager"):
                    pm = registry.get("provider_manager")
                    try:
                        p_obj = pm.get_provider(key_name)
                        if p_obj.is_available:
                            status_level = "STANDBY"
                            status_desc = "Configured (Standby)"
                        else:
                            status_level = "WARNING"
                            status_desc = "Not initialized"
                    except Exception as exc:
                        status_level = "ERROR"
                        status_desc = str(exc)[:40]
                else:
                    status_level = "UNKNOWN"
                    status_desc = "Provider manager not registered"

            checks[display_name] = {
                "status": status_level,
                "message": status_desc,
                "latency": latency_str,
                "last_error": last_err,
                "retry_after": retry_after,
            }

        return checks

    def check_memory(self) -> dict[str, Any]:
        """Check status of database stores, memory files, and vector backends."""
        checks = {
            "Memory Backend": "Local JSON store",
            "Semantic Search": "Disabled",
            "Stored Memories": "0 memories",
            "Memory File": "Unavailable",
            "Vector Backend": "Unavailable",
            "Memory Status": "Healthy"
        }

        try:
            from core.paths import MEMORY_DIR
            store_file = MEMORY_DIR / "memory_store.json"
            checks["Memory File"] = str(store_file)
            
            if store_file.exists():
                checks["Memory Status"] = "Healthy"
                import json
                try:
                    with open(store_file, "r") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        conversations = data.get("conversations", [])
                        facts = data.get("facts", {})
                        total_memories = len(conversations) + len(facts)
                        checks["Stored Memories"] = f"{total_memories} entries"
                    else:
                        checks["Stored Memories"] = "Invalid structure"
                except Exception as exc:
                    checks["Stored Memories"] = f"Read error: {exc}"
            else:
                checks["Memory Status"] = "Healthy (New)"
                checks["Stored Memories"] = "0 entries (no file)"
        except Exception as exc:
            checks["Memory Status"] = f"Failed: {exc}"

        # Vector store diagnostics
        try:
            if registry.exists("vector_store"):
                vs = registry.get("vector_store")
                if vs.health_check():
                    checks["Semantic Search"] = "Enabled"
                    checks["Vector Backend"] = "ChromaDB/Local (Active)"
        except Exception:
            pass

        return checks

    def check_environment(self) -> dict[str, Any]:
        """Verify environment files, configuration variables, and prompts structures."""
        checks = {
            ".env status": "Missing",
            "preferences.json": "Missing",
            "working_dirs": "Healthy"
        }

        # Check .env existence
        from core.paths import project_root
        env_file = project_root() / ".env"
        if env_file.exists():
            checks[".env status"] = "Present"
        
        # Check preferences.json existence
        from core.paths import PROMPTS_DIR
        pref_file = PROMPTS_DIR / "preferences.json"
        if pref_file.exists():
            checks["preferences.json"] = "Present"

        # Check directories
        from core.paths import _ALL_DIRECTORIES
        missing_dirs = [str(d) for d in _ALL_DIRECTORIES if not d.exists()]
        if missing_dirs:
            checks["working_dirs"] = f"Missing: {len(missing_dirs)} dirs"
        else:
            checks["working_dirs"] = "All dirs exist"

        return checks

    def get_performance(self) -> dict[str, Any]:
        """Gather process memory footprint and CPU utilization."""
        metrics = {
            "CPU": "N/A",
            "RAM": "N/A",
            "Threads": threading.active_count(),
            "PID": os.getpid(),
            "Python Memory": "N/A"
        }

        try:
            import psutil
            process = psutil.Process(os.getpid())
            metrics["CPU"] = f"{psutil.cpu_percent(interval=None)}%"
            metrics["RAM"] = f"{psutil.virtual_memory().percent}%"
            # Get resident memory in Megabytes
            mem_mb = process.memory_info().rss / (1024 * 1024)
            metrics["Python Memory"] = f"{mem_mb:.1f} MB"
        except Exception:
            pass

        return metrics
