"""Visual UI understanding, accessibility tree extraction, and error analysis for NOVA."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from core.logger import get_logger
from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
)
from providers.provider_manager import ProviderManager, TaskType

logger = get_logger(__name__)


class ScreenAnalyzer:
    """Extracts structured UI elements, visible text, dialogs, and errors from on-demand snapshots."""

    @classmethod
    def analyze_snapshot(
        cls,
        snapshot: ScreenSnapshot,
        provider_mgr: ProviderManager | None = None,
        deep_semantic: bool = False,
    ) -> ScreenAnalysis:
        """Perform structured UI extraction and semantic understanding on a snapshot."""
        analysis = ScreenAnalysis(snapshot=snapshot)

        # 1. Structured Accessibility Tree Extraction via System Events
        cls._extract_accessibility_ui_elements(analysis, snapshot)

        # 2. Extract error banners, dialogs, and visible text alerts
        cls._detect_dialogs_and_errors(analysis, snapshot)

        # 3. Deep AI Explanation via ProviderManager if requested
        if deep_semantic and provider_mgr:
            cls._perform_semantic_screen_analysis(analysis, snapshot, provider_mgr)

        logger.debug(
            "Screen analysis complete for %s: %d elements (%d buttons, %d inputs, %d errors)",
            snapshot.snapshot_id,
            len(analysis.ui_elements),
            len(analysis.buttons),
            len(analysis.inputs),
            len(analysis.errors),
        )
        return analysis

    @classmethod
    def _extract_accessibility_ui_elements(cls, analysis: ScreenAnalysis, snapshot: ScreenSnapshot) -> None:
        """Query macOS Accessibility API via AppleScript for frontmost application UI elements."""
        app_name = snapshot.active_application
        if not app_name:
            return

        script = f"""
        tell application "System Events"
            try
                set targetProc to first application process whose frontmost is true
                if not (exists front window of targetProc) then
                    return "NO_WINDOW"
                end if
                set frontWin to front window of targetProc
                set outList to {{}}
                
                -- Extract Buttons
                try
                    repeat with b in (buttons of frontWin)
                        set bName to name of b
                        if bName is missing value then set bName to description of b
                        if bName is missing value then set bName to ""
                        set bPos to position of b
                        set bSize to size of b
                        set end of outList to ("button:::" & bName & ":::" & (item 1 of bPos as text) & "," & (item 2 of bPos as text) & ":::" & (item 1 of bSize as text) & "," & (item 2 of bSize as text))
                    end repeat
                end try
                
                -- Extract Text Fields / Inputs
                try
                    repeat with tf in (text fields of frontWin)
                        set tfName to name of tf
                        if tfName is missing value then set tfName to description of tf
                        if tfName is missing value then set tfName to ""
                        set tfPos to position of tf
                        set tfSize to size of tf
                        set end of outList to ("input:::" & tfName & ":::" & (item 1 of tfPos as text) & "," & (item 2 of tfPos as text) & ":::" & (item 1 of tfSize as text) & "," & (item 2 of tfSize as text))
                    end repeat
                end try

                -- Extract Popups / Sheets / Dialogs
                try
                    repeat with sh in (sheets of frontWin)
                        set shName to name of sh
                        if shName is missing value then set shName to "Sheet Popup"
                        set shPos to position of sh
                        set shSize to size of sh
                        set end of outList to ("popup:::" & shName & ":::" & (item 1 of shPos as text) & "," & (item 2 of shPos as text) & ":::" & (item 1 of shSize as text) & "," & (item 2 of shSize as text))
                    end repeat
                end try

                -- Extract Checkboxes / Radio buttons
                try
                    repeat with cb in (checkboxes of frontWin)
                        set cbName to name of cb
                        if cbName is missing value then set cbName to ""
                        set cbPos to position of cb
                        set cbSize to size of cb
                        set end of outList to ("checkbox:::" & cbName & ":::" & (item 1 of cbPos as text) & "," & (item 2 of cbPos as text) & ":::" & (item 1 of cbSize as text) & "," & (item 2 of cbSize as text))
                    end repeat
                end try

                -- Extract Links / Static Texts with actions
                try
                    repeat with st in (static texts of frontWin)
                        set stName to value of st
                        if stName is not missing value and length of (stName as text) > 0 and length of (stName as text) < 80 then
                            set stPos to position of st
                            set stSize to size of st
                            set end of outList to ("text:::" & (stName as text) & ":::" & (item 1 of stPos as text) & "," & (item 2 of stPos as text) & ":::" & (item 1 of stSize as text) & "," & (item 2 of stSize as text))
                        end if
                    end repeat
                end try

                set AppleScript's text item delimiters to "|||"
                return (outList as text)
            on error errMsg
                return "ERROR:::" & errMsg
            end try
        end tell
        """
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2.5)
            raw = res.stdout.strip()
            if not raw or raw.startswith("NO_WINDOW") or raw.startswith("ERROR:::"):
                return

            items = raw.split("|||")
            for item in items:
                parts = item.split(":::")
                if len(parts) >= 4:
                    elem_type_str = parts[0].strip().lower()
                    label = parts[1].strip()
                    pos_parts = [int(p.strip()) for p in parts[2].split(",") if p.strip().lstrip("-").isdigit()]
                    size_parts = [int(p.strip()) for p in parts[3].split(",") if p.strip().lstrip("-").isdigit()]

                    if len(pos_parts) == 2 and len(size_parts) == 2:
                        x, y = pos_parts[0], pos_parts[1]
                        w, h = size_parts[0], size_parts[1]

                        # Ignore invalid coordinates
                        if w <= 0 or h <= 0 or x < 0 or y < 0:
                            continue

                        etype = UIElementType.BUTTON if elem_type_str == "button" else \
                                UIElementType.INPUT if elem_type_str == "input" else \
                                UIElementType.POPUP if elem_type_str == "popup" else \
                                UIElementType.CHECKBOX if elem_type_str == "checkbox" else \
                                UIElementType.TEXT if elem_type_str == "text" else UIElementType.UNKNOWN

                        element = UIElement.create(
                            element_type=etype,
                            label=label,
                            x=x,
                            y=y,
                            w=w,
                            h=h,
                            confidence=0.98,
                            source="accessibility",
                            raw_text=label,
                        )
                        analysis.ui_elements.append(element)
                        if etype == UIElementType.BUTTON:
                            analysis.buttons.append(element)
                        elif etype == UIElementType.INPUT:
                            analysis.inputs.append(element)
                        elif etype == UIElementType.POPUP:
                            analysis.dialogs.append(element)
                        elif etype == UIElementType.TEXT and label:
                            analysis.visible_text.append(label)

        except Exception as exc:
            logger.debug("Accessibility extraction exception: %s", exc)

    @classmethod
    def _detect_dialogs_and_errors(cls, analysis: ScreenAnalysis, snapshot: ScreenSnapshot) -> None:
        """Scan active window title, accessibility text, and UI elements for error patterns."""
        win_title = snapshot.active_window.lower()
        err_keywords = ["error", "fatal", "exception", "failed", "warning", "traceback", "cannot", "denied", "not found", "404", "500"]

        if any(k in win_title for k in err_keywords):
            analysis.errors.append(snapshot.active_window)

        # Check detected static texts for errors
        for text_item in analysis.visible_text:
            t_lower = text_item.lower()
            if any(k in t_lower for k in err_keywords) and len(text_item) > 4:
                if text_item not in analysis.errors:
                    analysis.errors.append(text_item)

    @classmethod
    def _perform_semantic_screen_analysis(
        cls,
        analysis: ScreenAnalysis,
        snapshot: ScreenSnapshot,
        provider_mgr: ProviderManager,
    ) -> None:
        """Use ProviderManager to synthesize high-level description and error explanations."""
        context_desc = (
            f"Active Application: {snapshot.active_application}\n"
            f"Active Window: {snapshot.active_window}\n"
            f"Detected UI Elements: {len(analysis.ui_elements)}\n"
            f"Visible Text Samples: {', '.join(analysis.visible_text[:10])}\n"
            f"Detected Errors: {', '.join(analysis.errors) if analysis.errors else 'None'}"
        )

        prompt = (
            f"You are NOVA's visual brain. Briefly summarize the user's screen context in 2 concise sentences based on this metadata:\n"
            f"{context_desc}"
        )

        try:
            resp = provider_mgr.generate_response(
                prompt=prompt,
                system_prompt="You are NOVA, a smart computer agent. Be concise, direct, and factual.",
                task_type=TaskType.FAST,
            )
            analysis.description = resp.strip()
        except Exception as exc:
            logger.debug("Semantic screen analysis generation failed: %s", exc)
            analysis.description = f"User is viewing {snapshot.active_window or snapshot.active_application}."

    @classmethod
    def explain_error_on_screen(
        cls,
        analysis: ScreenAnalysis,
        provider_mgr: ProviderManager,
    ) -> str:
        """Generate a user-friendly spoken explanation of detected errors on screen."""
        if not analysis.errors and not any("error" in t.lower() for t in analysis.visible_text):
            return f"I don't see any explicit error messages in your active window ({analysis.snapshot.active_window or analysis.snapshot.active_application})."

        error_context = "\n".join(analysis.errors) if analysis.errors else "\n".join(analysis.visible_text[:10])
        prompt = (
            f"Explain the following error from the user's screen clearly and suggest a quick fix in 2 short conversational sentences:\n"
            f"Application: {analysis.snapshot.active_application}\n"
            f"Error details:\n{error_context}"
        )

        try:
            return provider_mgr.generate_response(
                prompt=prompt,
                system_prompt="You are NOVA. Explain software errors simply and clearly without jargon.",
                task_type=TaskType.GENERAL,
            )
        except Exception as exc:
            logger.error("Failed to generate error explanation: %s", exc)
            return f"I noticed an error in {analysis.snapshot.active_application}: {analysis.errors[0] if analysis.errors else 'Unknown error'}."
