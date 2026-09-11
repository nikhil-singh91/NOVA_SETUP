"""System clipboard read, write, and clear operations using pbcopy and pbpaste."""

from __future__ import annotations

import subprocess
from mac_control.models import ExecutionResult, ExecutionStatus, CommandCategory, MacCommand

def execute_clipboard_command(cmd: MacCommand) -> ExecutionResult:
    """Execute system clipboard buffer operations."""
    action = cmd.action
    args = cmd.args
    
    try:
        if action == "copy":
            text = args.get("text", "").strip()
            if not text:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="No text specified to copy",
                    command_name="Copy to Clipboard",
                    category=CommandCategory.CLIPBOARD
                )
            
            # Pipe text to pbcopy
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            
            # Truncate text preview for details message
            preview = text if len(text) <= 30 else text[:27] + "..."
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Copied to clipboard: '{preview}'",
                command_name="Copy to Clipboard",
                category=CommandCategory.CLIPBOARD,
                details={"text": text}
            )
            
        elif action == "paste" or action == "read":
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
            clip_text = res.stdout.strip()
            
            # Truncate text preview for details message
            preview = clip_text if len(clip_text) <= 30 else clip_text[:27] + "..."
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Clipboard content: '{preview}'" if clip_text else "Clipboard is empty",
                command_name="Read Clipboard",
                category=CommandCategory.CLIPBOARD,
                details={"text": clip_text}
            )
            
        elif action == "clear":
            # Pipe empty string to pbcopy
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            process.communicate(input="")
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Clipboard cleared",
                command_name="Clear Clipboard",
                category=CommandCategory.CLIPBOARD
            )
            
    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Clipboard operation failed: {exc}",
            command_name="Clipboard Control",
            category=CommandCategory.CLIPBOARD
        )
        
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown clipboard action: {action}",
        command_name="Clipboard Control",
        category=CommandCategory.CLIPBOARD
    )


def get_clipboard() -> str:
    """Return text currently stored in the macOS pasteboard."""
    try:
        res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
        return res.stdout
    except Exception:
        return ""


def set_clipboard(text: str) -> bool:
    """Set text in the macOS pasteboard."""
    try:
        process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=text or "")
        return True
    except Exception:
        return False


def clear_clipboard() -> bool:
    """Empty the macOS pasteboard."""
    return set_clipboard("")
