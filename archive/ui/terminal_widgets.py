"""Pre-designed terminal UI card panels and layouts using Unicode box framing."""

from __future__ import annotations

import re
from typing import Any

from ui.terminal_theme import TerminalTheme as T

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def visible_length(text: str) -> int:
    """Return the screen column length of a string, ignoring ANSI escape colors."""
    return len(ANSI_ESCAPE.sub('', text))


def draw_box(title: str, lines: list[str], width: int) -> list[str]:
    """Frame lines inside a Unicode box panel of a fixed width.

    Properly handles ANSI colors when measuring content spacing.
    """
    content_width = width - 4
    box = []

    # Format header border
    header_title = f" {title} "
    title_len = len(header_title)
    if title_len > content_width:
        header_title = header_title[:content_width]
        title_len = len(header_title)

    left_padding = 2
    right_padding = content_width - left_padding - title_len

    top_line = (
        T.TL +
        T.H * left_padding +
        T.colorize(header_title, T.CYAN + T.BOLD) +
        T.H * right_padding +
        T.TR
    )
    box.append(top_line)

    # Format content lines
    for line in lines:
        vis_len = visible_length(line)
        if vis_len > content_width:
            # Simple truncation while preserving basic escape characters if possible
            # (or just strip raw line and pad)
            line = line[:content_width]
            vis_len = visible_length(line)

        pad_size = content_width - vis_len
        box.append(f"{T.V} {line}{' ' * pad_size} {T.V}")

    # Format bottom border
    box.append(T.BL + T.H * (content_width + 2) + T.BR)
    return box


def get_status_indicator(status: str) -> str:
    """Format status strings to neon colorized bullet symbols."""
    status_lower = status.lower()
    if "healthy" in status_lower or "granted" in status_lower or "connected" in status_lower or "present" in status_lower:
        return T.colorize("✅ Healthy", T.GREEN)
    elif "warning" in status_lower or "exceeded" in status_lower or "busy" in status_lower or "offline" in status_lower:
        return T.colorize("⚠️  Warning", T.YELLOW)
    elif "failed" in status_lower or "missing" in status_lower or "denied" in status_lower:
        return T.colorize("❌ Failed", T.RED)
    elif "coming soon" in status_lower:
        return T.colorize("🚧 Coming Soon", T.GRAY)
    return T.colorize(status, T.BLUE)


def make_header_card(sys_info: dict[str, Any], width: int) -> list[str]:
    """Generate the ASCII art space header logo and main metadata details."""
    logo = [
        r"  _   _  ____     __  _          ",
        r" | \ | |/ __ \    \ \/ /   /\    ",
        r" |  \| | |  | |___ \  /   /  \   ",
        r" | . ` | |  | / __|/  \  / /\ \  ",
        r" | |\  | |__| \__ / /\ \/ ____ \ ",
        r" |_| \_|\____/|___/_/  \_/_/    \_\ "
    ]

    # Center ASCII logo
    centered_logo = []
    for line in logo:
        pad = max(0, (width - len(line)) // 2)
        centered_logo.append(T.colorize(" " * pad + line, T.CYAN + T.BOLD))

    # Details block
    info_lines = [
        f" {T.colorize('NOVA OS ORCHESTRATOR', T.BOLD)}",
        f" Hostname:    {T.colorize(sys_info.get('hostname', 'localhost'), T.DARK_CYAN)}",
        f" User:        {sys_info.get('user', 'admin')}",
        f" System Mode: {T.colorize('DEVELOPMENT', T.YELLOW + T.BOLD) if sys_info.get('debug', False) else T.colorize('PRODUCTION', T.GREEN + T.BOLD)}",
        f" Platform:    {sys_info.get('os', 'macOS')} ({sys_info.get('arch', 'arm64')})",
        f" Python:      {sys_info.get('python', '3.12')}"
    ]

    box_lines = draw_box("CORE DASHBOARD", info_lines, width)
    return centered_logo + [""] + box_lines


def make_health_card(health_results: dict[str, Any], width: int) -> list[str]:
    """Generate the card summarizing actual subsystems health status."""
    lines = []
    core_results = health_results.get("core", {})

    for display_name, result in core_results.items():
        status_ind = get_status_indicator(result.get("status", "Healthy"))
        msg = result.get("message", "")
        # Limit msg size to fit in column nicely
        if len(msg) > 30:
            msg = msg[:27] + "..."
        lines.append(f" {display_name:<20} {status_ind:<15} {T.colorize(msg, T.GRAY)}")

    return draw_box("SYSTEM HEALTH CHECK", lines, width)


def make_voice_card(voice_results: dict[str, Any], width: int) -> list[str]:
    """Format and print voice speech configuration and permissions status."""
    lines = [
        f" STT Engine:     {T.colorize(voice_results.get('Speech Engine', 'Whisper'), T.BOLD)}",
        f" TTS Engine:     {voice_results.get('Voice Engine', 'Edge-TTS')}",
        f" Rate/Speed:     {voice_results.get('Speech Rate', '1.0x')}",
        f" Language:       {voice_results.get('Language', 'en-US')}",
        f" Microphone:     {T.colorize(voice_results.get('Microphone', 'N/A'), T.DARK_CYAN)}",
        f" Speaker:        {voice_results.get('Speaker', 'N/A')}",
        f" Mic Status:     {get_status_indicator(voice_results.get('Microphone Permission', 'Granted'))}",
        f" Speaker Status: {get_status_indicator(voice_results.get('Speaker Permission', 'Granted'))}"
    ]
    return draw_box("VOICE SYSTEMS", lines, width)


def make_providers_card(provider_results: dict[str, Any], width: int) -> list[str]:
    """Show details of configured AI LLM providers and connection diagnostics."""
    lines = []

    # Connection indicators
    for name in ["Gemini", "Groq", "OpenRouter", "Cerebras"]:
        info = provider_results.get(name, {"status": "Warning", "message": "API key missing"})
        indicator = get_status_indicator(info.get("status"))
        msg = info.get("message", "")
        lines.append(f" {name:<12} {indicator:<15} {T.colorize(msg, T.GRAY)}")

    return draw_box("AI PROVIDERS", lines, width)


def make_memory_card(memory_results: dict[str, Any], width: int) -> list[str]:
    """Render memory storage sizes, backend database, and vector paths."""
    lines = [
        f" Backend Store:  {T.colorize(memory_results.get('Memory Backend', 'JSON'), T.BOLD)}",
        f" Vector DB:      {memory_results.get('Semantic Search', 'Disabled')}",
        f" Memory Entries: {T.colorize(memory_results.get('Stored Memories', '0 entries'), T.GREEN)}",
        f" Memory Status:  {get_status_indicator(memory_results.get('Memory Status', 'Healthy'))}",
        f" Vector Engine:  {memory_results.get('Vector Backend', 'N/A')}"
    ]
    return draw_box("MEMORY LAYER", lines, width)


def make_performance_card(perf_results: dict[str, Any], width: int) -> list[str]:
    """Format running process metrics (CPU/RAM/Threads)."""
    lines = [
        f" CPU Util:       {T.colorize(perf_results.get('CPU', '0%'), T.DARK_CYAN)}",
        f" RAM Util:       {perf_results.get('RAM', '0%')}",
        f" Active Threads: {perf_results.get('Threads', '0')}",
        f" Process ID:     {perf_results.get('PID', '0')}",
        f" Process RSS:    {T.colorize(perf_results.get('Python Memory', '0 MB'), T.BOLD)}"
    ]
    return draw_box("PERFORMANCE DIAGNOSTICS", lines, width)


def make_future_tech_card(width: int) -> list[str]:
    """Reserved tech stack grid showing placeholders for future implementations."""
    tech_modules = [
        "Internet Services", "Computer Vision", "Camera Analytics",
        "Automation Engine", "Plugin Loader", "Calendar Actions",
        "Browser Controller", "Smart Home Control", "Sound & Music"
    ]
    lines = []
    coming_soon = get_status_indicator("coming soon")
    for module in tech_modules:
        lines.append(f" {module:<25} {coming_soon}")
    return draw_box("FUTURE TECHNOLOGY & CORE MODULES", lines, width)
