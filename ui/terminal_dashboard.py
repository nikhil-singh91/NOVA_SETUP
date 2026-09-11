"""NOVA Rich Terminal Operations Dashboard & Live User Activity Feed."""

from __future__ import annotations

import getpass
import os
import platform
import shutil
import socket
import sys
import threading
import time
from collections import deque
from typing import Any

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import ProgressBar
from rich.table import Table
from rich.text import Text

from config.settings import settings
from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from ui.health_checker import (
    ActivityInteraction,
    ActivityStep,
    DashboardStatsManager,
    HealthChecker,
    LogEntry,
)

logger = get_logger(__name__)


class TerminalDashboard:
    """Coordinates and renders the rich real-time command operations center & user activity feed."""

    _instance: TerminalDashboard | None = None

    def __init__(self) -> None:
        TerminalDashboard._instance = self
        self.checker = HealthChecker()
        self.console = Console()
        self._running = False
        self._updater_thread: threading.Thread | None = None
        self._lock = threading.RLock()

        # Activity Feed Navigation & Display State
        self.auto_scroll: bool = True
        self.scroll_offset: int = 0
        self.filter_mode: str = "ACTIVITY"  # ACTIVITY | YOU | UNDERSTOOD | ACTION | NOVA | RESULT | ERROR | DEBUG | RAW | ALL
        self.search_query: str = ""
        self.maximized: bool = False
        self._last_draw_time: float = 0.0

    @classmethod
    def get_instance(cls) -> TerminalDashboard | None:
        """Access the active terminal dashboard singleton."""
        return cls._instance

    def start(self) -> None:
        """Start background update loops and event subscriptions."""
        with self._lock:
            if self._running:
                return
            self._running = True

            # Register activity and log callbacks for immediate live streaming
            DashboardStatsManager.register_activity_callback(self._on_activity_event)
            DashboardStatsManager.register_log_callback(self._on_raw_log)

            # Subscribe to EventBus for real-time reactivity
            try:
                if registry.exists("event_bus"):
                    bus = registry.get("event_bus")
                    bus.subscribe(NovaEvent.STATE_CHANGED, self.handle_event)
                    bus.subscribe(NovaEvent.THINKING_STARTED, self.handle_event)
                    bus.subscribe(NovaEvent.RESPONSE_GENERATED, self.handle_event)
                    bus.subscribe(NovaEvent.SPEAKING_STARTED, self.handle_event)
                    bus.subscribe(NovaEvent.SPEAKING_FINISHED, self.handle_event)
                    bus.subscribe(NovaEvent.COMMAND_EXECUTED, self.handle_event)
                    bus.subscribe(NovaEvent.BROWSER_ACTION_STARTED, self.handle_event)
                    bus.subscribe(NovaEvent.BROWSER_ACTION_COMPLETED, self.handle_event)
                    bus.subscribe(NovaEvent.DESKTOP_ACTION_STARTED, self.handle_event)
                    bus.subscribe(NovaEvent.DESKTOP_ACTION_COMPLETED, self.handle_event)
            except Exception as e:
                logger.warning("Failed to subscribe dashboard to event bus: %s", e)

            self._updater_thread = threading.Thread(
                target=self._run_updater, daemon=True, name="nova-dashboard-updater"
            )
            self._updater_thread.start()

    def stop(self) -> None:
        """Stop background diagnostic loops."""
        with self._lock:
            self._running = False
            DashboardStatsManager.unregister_activity_callback(self._on_activity_event)
            DashboardStatsManager.unregister_log_callback(self._on_raw_log)
        if self._updater_thread:
            self._updater_thread.join(timeout=0.2)
            self._updater_thread = None

    def _on_activity_event(self, step: ActivityStep, interaction: ActivityInteraction) -> None:
        """Trigger instant redraw when a user activity event occurs."""
        if not self._running or not self.auto_scroll:
            return
        now = time.monotonic()
        if now - self._last_draw_time > 0.05:
            self.draw_dashboard()

    def _on_raw_log(self, entry: LogEntry) -> None:
        """Trigger redraw when a raw debug log arrives and debug view is active."""
        if not self._running or not self.auto_scroll:
            return
        if self.filter_mode in ("DEBUG", "RAW"):
            now = time.monotonic()
            if now - self._last_draw_time > 0.05:
                self.draw_dashboard()

    # -------------------------------------------------------------------------
    # Activity Feed Navigation & Control Methods
    # -------------------------------------------------------------------------

    def scroll_up(self, lines: int = 5) -> None:
        """Scroll backward through activity history and pause auto-scroll."""
        with self._lock:
            self.auto_scroll = False
            self.scroll_offset += max(1, lines)
        self.draw_dashboard()

    def scroll_down(self, lines: int = 5) -> None:
        """Scroll forward through activity history; resume auto-scroll if at newest entry."""
        with self._lock:
            self.scroll_offset = max(0, self.scroll_offset - max(1, lines))
            if self.scroll_offset == 0:
                self.auto_scroll = True
        self.draw_dashboard()

    def jump_to_latest(self) -> None:
        """Jump to the newest activity entries and resume live auto-scroll."""
        with self._lock:
            self.scroll_offset = 0
            self.auto_scroll = True
        self.draw_dashboard()

    def jump_to_top(self) -> None:
        """Jump to the oldest available activity entries and pause auto-scroll."""
        with self._lock:
            self.auto_scroll = False
            self.scroll_offset = 100000
        self.draw_dashboard()

    def clear_feed(self) -> None:
        """Clear user activity feed display."""
        DashboardStatsManager.clear_activities()
        self.jump_to_latest()

    def clear_logs(self) -> None:
        """Clear both activity feed and raw debug logs."""
        DashboardStatsManager.clear_logs()
        self.jump_to_latest()

    @property
    def level_filter(self) -> str:
        return self.filter_mode

    @level_filter.setter
    def level_filter(self, val: str) -> None:
        self.filter_mode = val.upper()

    def set_level_filter(self, level: str) -> None:
        """Backward-compatible alias for set_filter_mode."""
        self.set_filter_mode(level)

    def set_filter_mode(self, mode: str) -> None:
        """Set active view filter (ACTIVITY | YOU | UNDERSTOOD | ACTION | NOVA | RESULT | ERROR | DEBUG | ALL)."""
        with self._lock:
            self.filter_mode = mode.upper()
            self.scroll_offset = 0
            self.auto_scroll = True
        self.draw_dashboard()

    def cycle_filter(self) -> str:
        """Cycle through user-friendly activity filters."""
        modes = ["ACTIVITY", "YOU", "UNDERSTOOD", "ACTION", "NOVA", "RESULT", "ERROR", "DEBUG", "ALL"]
        current_idx = modes.index(self.filter_mode) if self.filter_mode in modes else 0
        next_mode = modes[(current_idx + 1) % len(modes)]
        self.set_filter_mode(next_mode)
        return next_mode

    def set_search_query(self, query: str) -> None:
        """Set text search filter for activity messages."""
        with self._lock:
            self.search_query = query.strip()
            self.scroll_offset = 0
            self.auto_scroll = True
        self.draw_dashboard()

    def toggle_maximize(self) -> bool:
        """Toggle fullscreen Activity Feed view vs split dashboard view."""
        with self._lock:
            self.maximized = not self.maximized
        self.draw_dashboard()
        return self.maximized

    def copy_to_clipboard(self) -> bool:
        """Copy formatted activity feed to macOS clipboard."""
        if self.filter_mode in ("DEBUG", "RAW"):
            return DashboardStatsManager.copy_to_clipboard(search_query=self.search_query)
        return DashboardStatsManager.copy_activity_to_clipboard()

    # -------------------------------------------------------------------------
    # Event Bus Subscription Handling
    # -------------------------------------------------------------------------

    def handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Process event ticks and redraw dashboard."""
        try:
            if event_name == NovaEvent.STATE_CHANGED.value:
                new_state = payload.get("new_state", "LISTENING")
                DashboardStatsManager.update("voice_state", new_state)
                if new_state == "THINKING":
                    DashboardStatsManager.update("current_task", "Thinking...")
                elif new_state == "SPEAKING":
                    DashboardStatsManager.update("current_task", "Speaking...")
                elif new_state == "LISTENING":
                    DashboardStatsManager.update("current_task", "Waiting for input")
                elif new_state == "GREETING":
                    DashboardStatsManager.update("current_task", "Greeting user...")
                elif new_state == "INITIALIZE":
                    DashboardStatsManager.update("current_task", "Initializing...")

            elif event_name == NovaEvent.THINKING_STARTED.value:
                DashboardStatsManager.update("current_task", "Thinking...")

            elif event_name == NovaEvent.RESPONSE_GENERATED.value:
                DashboardStatsManager.update("current_task", "Responding...")

            elif event_name == NovaEvent.SPEAKING_STARTED.value:
                DashboardStatsManager.update("current_task", "Speaking...")

            elif event_name == NovaEvent.SPEAKING_FINISHED.value:
                DashboardStatsManager.update("current_task", "Waiting for input")

            elif event_name == NovaEvent.COMMAND_EXECUTED.value:
                cmd_name = payload.get("command", "None")
                cmd_cat = payload.get("category", "None")
                cmd_time = payload.get("execution_time_ms", 0)
                cmd_status = payload.get("status", "SUCCESS")
                cmd_result = payload.get("result", "Done")

                DashboardStatsManager.update("last_command", cmd_name)
                DashboardStatsManager.update("command_category", cmd_cat)
                DashboardStatsManager.update("command_execution_time", f"{cmd_time} ms")
                DashboardStatsManager.update("command_status", cmd_status)
                DashboardStatsManager.update("command_result", cmd_result)
                DashboardStatsManager.update("current_task", f"Completed: {cmd_name}")

            self.draw_dashboard()
        except Exception as e:
            logger.error("Error processing dashboard event: %s", e)

    def _run_updater(self) -> None:
        """Periodically refresh health checks and redraw layout."""
        last_check = 0.0
        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                now = time.monotonic()
                if now - last_check > 5.0:
                    self.checker.run_checks_async()
                    last_check = now
                time.sleep(1.0)
                self.draw_dashboard()
            except Exception as e:
                logger.error("Error in dashboard updater loop: %s", e)

    def render(self) -> None:
        """Draw diagnostic screen and start background updater."""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        self.checker.run_checks_async()
        self.draw_dashboard()
        self.start()

    # -------------------------------------------------------------------------
    # Dashboard Layout Rendering
    # -------------------------------------------------------------------------

    def draw_dashboard(self) -> None:
        """Assemble grid panels and draw them in place using ANSI cursor overrides."""
        try:
            with self._lock:
                self._last_draw_time = time.monotonic()

            terminal_size = shutil.get_terminal_size((110, 36))
            term_lines = max(24, terminal_size.lines)

            # Gathers system results
            results = self.checker.run_all_checks()
            stats = DashboardStatsManager.get_all()

            # -----------------------------------------------------------------
            # 1. Root Layout Construction
            # -----------------------------------------------------------------
            layout = Layout()

            if self.maximized:
                # Maximized Activity View: compact top bar + full activity feed
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="activity_feed"),
                    Layout(name="footer", size=1),
                )
            else:
                # Standard Overview:
                # Header (top)
                # Middle Grid (Voice | AI Providers | System Performance)
                # Lower Grid (Memory | Mac Control | Recovery)
                # Bottom / Large: Full-width Live Activity Feed
                # Footer (bottom)
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="middle_grid", size=10),
                    Layout(name="lower_grid", size=6),
                    Layout(name="activity_feed"),
                    Layout(name="footer", size=1),
                )

                layout["middle_grid"].split_row(
                    Layout(name="voice", ratio=1),
                    Layout(name="ai_providers", ratio=1),
                    Layout(name="system", ratio=1),
                )

                layout["lower_grid"].split_row(
                    Layout(name="memory", ratio=1),
                    Layout(name="commands", ratio=1),
                    Layout(name="recovery", ratio=1),
                )

            # -----------------------------------------------------------------
            # 2. Header Panel
            # -----------------------------------------------------------------
            uptime_sec = int(time.time() - stats.get("session_start_time", time.time()))
            uptime_str = f"{uptime_sec // 60}m {uptime_sec % 60}s"
            header_table = Table.grid(expand=True)
            header_table.add_column(justify="left", style="bold cyan")
            header_table.add_column(justify="center", style="dim")
            header_table.add_column(justify="right", style="cyan")

            header_table.add_row(
                "🚀 NOVA OPERATIONS CONTROL CENTER",
                f"Uptime: {uptime_str} │ User: {getpass.getuser()} │ Host: {socket.gethostname()}",
                f"{time.strftime('%Y-%m-%d %H:%M:%S')}",
            )
            layout["header"].update(Panel(header_table, border_style="cyan", padding=(0, 1)))

            # -----------------------------------------------------------------
            # 3. Middle & Lower Monitoring Grids (if not maximized)
            # -----------------------------------------------------------------
            if not self.maximized:
                # A. Voice Subsystem Panel (Middle Left)
                voice_spec = results.get("voice", {})
                state_val = stats.get("voice_state", "IDLE")

                if state_val == "SPEAKING":
                    wave_txt = "[bold green]▅▅▃▆▃▅▃▆▃▅▃▆▃▅[/bold green]"
                elif state_val == "LISTENING":
                    wave_txt = "[bold cyan] ▃▂ ▂▃▂ ▂▃▂ ▂ [/bold cyan]"
                elif state_val == "THINKING":
                    wave_txt = "[bold yellow] ░░░░░░░░░░░░░ [/bold yellow]"
                else:
                    wave_txt = "[dim]--------------[/dim]"

                audio_level = stats.get("audio_level", 0 if state_val == "IDLE" else 15)
                audio_bar = ProgressBar(total=100, completed=audio_level, width=10)

                voice_table = Table.grid(expand=True)
                voice_table.add_column(style="bold dim", width=14)
                voice_table.add_column(style="bold")
                voice_table.add_row("Voice State:", f"[bold green]{state_val}[/bold green]" if state_val != "ERROR" else f"[bold red]{state_val}[/bold red]")
                voice_table.add_row("Microphone:", stats.get("mic_state", "STANDBY"))
                voice_table.add_row("Whisper Engine:", str(voice_spec.get("Speech Engine", "Local Whisper"))[:18])
                voice_table.add_row("Speech Conf:", stats.get("speech_confidence", "N/A"))
                voice_table.add_row("Audio Level:", audio_bar)
                voice_table.add_row("Waveform:", wave_txt)
                layout["voice"].update(Panel(voice_table, title="🎙️ Voice", border_style="green" if state_val != "ERROR" else "red"))

                # B. AI Providers Panel (Middle Center)
                prov_spec = results.get("providers", {})
                live_prov_stats = DashboardStatsManager.get_provider_stats()
                prov_table = Table(expand=True, box=None, padding=(0, 1))
                prov_table.add_column("Provider", style="bold", width=11)
                prov_table.add_column("Status", justify="center", width=14)
                prov_table.add_column("Latency", justify="right")

                for prov in ["Gemini", "Groq", "OpenRouter", "Cerebras"]:
                    p_key = prov.lower()
                    live_d = live_prov_stats.get(p_key, {})
                    diag_d = prov_spec.get(prov, {})
                    
                    status_lbl = (live_d.get("status") if live_d.get("status") and live_d.get("status") != "UNKNOWN" else diag_d.get("status", "UNKNOWN")).upper()
                    lat_str = live_d.get("latency") or diag_d.get("latency", "N/A")

                    if status_lbl == "HEALTHY":
                        status_fmt = "[bold green]HEALTHY[/bold green]"
                    elif status_lbl in ("QUOTA EXCEEDED", "RATE LIMITED", "RATE_LIMITED", "QUOTA_EXCEEDED"):
                        status_fmt = f"[bold yellow]{status_lbl}[/bold yellow]"
                    elif status_lbl in ("WARNING", "DEGRADED"):
                        status_fmt = f"[yellow]{status_lbl}[/yellow]"
                    elif status_lbl in ("STANDBY",):
                        status_fmt = "[dim cyan]STANDBY[/dim cyan]"
                    elif status_lbl in ("OFFLINE", "ERROR", "FAILED", "UNAVAILABLE", "AUTH_ERROR", "NETWORK_ERROR", "TIMEOUT", "CONFIG_ERROR"):
                        status_fmt = f"[bold red]{status_lbl}[/bold red]"
                    else:
                        status_fmt = f"[dim cyan]{status_lbl}[/dim cyan]"

                    prov_table.add_row(prov, status_fmt, lat_str)

                act_p = stats.get("active_provider", "Gemini")
                if stats.get("fallback_active"):
                    prov_title = f"🧠 AI (Active: {act_p} │ [bold green]FALLBACK ACTIVE[/bold green])"
                else:
                    prov_title = f"🧠 AI ({act_p})"

                layout["ai_providers"].update(Panel(prov_table, title=prov_title, border_style="cyan"))

                # C. System Performance Specs (Middle Right)
                perf_spec = results.get("performance", {})
                cpu_val_str = str(perf_spec.get("CPU", "0%")).replace("%", "")
                ram_val_str = str(perf_spec.get("RAM", "0%")).replace("%", "")
                try:
                    cpu_val = float(cpu_val_str)
                except ValueError:
                    cpu_val = 0.0
                try:
                    ram_val = float(ram_val_str)
                except ValueError:
                    ram_val = 0.0

                cpu_bar = ProgressBar(total=100, completed=cpu_val, width=10)
                ram_bar = ProgressBar(total=100, completed=ram_val, width=10)

                sys_table = Table.grid(expand=True)
                sys_table.add_column(style="bold dim", width=14)
                sys_table.add_column(style="bold")
                sys_table.add_row("CPU Load:", cpu_bar)
                sys_table.add_row("RAM Usage:", ram_bar)
                sys_table.add_row("Python Memory:", str(perf_spec.get("Python Memory", "N/A")))
                sys_table.add_row("Threads:", str(perf_spec.get("Threads", 0)))
                sys_table.add_row("Network:", "[bold green]CONNECTED[/bold green]" if prov_spec.get("Internet", {}).get("status") == "Healthy" else "[bold red]OFFLINE[/bold red]")
                layout["system"].update(Panel(sys_table, title="⚡ System Performance", border_style="yellow"))

                # D. Memory Layer Panel (Lower Left)
                mem_spec = results.get("memory", {})
                mem_table = Table.grid(expand=True)
                mem_table.add_column(style="bold dim", width=14)
                mem_table.add_column(style="bold")
                mem_table.add_row("Store:", mem_spec.get("Memory Backend", "Local JSON"))
                mem_table.add_row("Semantic DB:", mem_spec.get("Semantic Search", "ChromaDB"))
                mem_table.add_row("Memories:", str(mem_spec.get("Stored Memories", "0 entries")))
                mem_table.add_row("Store Status:", f"[bold green]{mem_spec.get('Memory Status', 'Healthy')}[/bold green]")
                layout["memory"].update(Panel(mem_table, title="💾 Memory Layer", border_style="blue"))

                # E. Mac Control Commands Panel (Lower Center)
                cmd_table = Table.grid(expand=True)
                cmd_table.add_column(style="bold dim", width=14)
                cmd_table.add_column(style="bold")

                last_c = stats.get("last_command", "None")
                if len(last_c) > 28:
                    last_c = last_c[:25] + "..."
                cmd_table.add_row("Last Command:", f"[bold green]{last_c}[/bold green]")

                raw_mac_intent = stats.get("mac_intent")
                intent_val = (raw_mac_intent if raw_mac_intent and raw_mac_intent != "None" else None) or stats.get("command_category") or "None"
                if len(intent_val) > 28:
                    intent_val = intent_val[:25] + "..."
                cmd_table.add_row("Intent:", intent_val)

                stat_val = stats.get("command_status", "IDLE")
                lat_m = stats.get("mac_latency", "N/A")
                if stat_val in ("SUCCESS", "COMPLETED"):
                    stat_fmt = f"[bold bright_green]SUCCESS[/bold bright_green] ({lat_m})"
                elif stat_val in ("FAILED", "PERMISSION_DENIED"):
                    stat_fmt = f"[bold red]FAILED[/bold red] ({lat_m})"
                elif stat_val in ("EXECUTING", "RECORDING"):
                    stat_fmt = f"[bold yellow]{stat_val}[/bold yellow]..."
                else:
                    stat_fmt = stat_val

                cmd_table.add_row("Status:", stat_fmt)

                raw_mac_res = stats.get("mac_result")
                res_msg = (raw_mac_res if raw_mac_res and raw_mac_res != "None" else None) or stats.get("command_result") or "None"
                if len(res_msg) > 28:
                    res_msg = res_msg[:25] + "..."
                cmd_table.add_row("Result:", res_msg)

                access_state = DashboardStatsManager.check_mac_control_access()
                if "GRANTED" in access_state:
                    access_fmt = "[bold green]GRANTED[/bold green]"
                elif "DENIED" in access_state:
                    access_fmt = "[bold red]DENIED[/bold red]"
                else:
                    access_fmt = f"[yellow]{access_state}[/yellow]"
                cmd_table.add_row("Access:", access_fmt)

                eyes_info = DashboardStatsManager.get_eyes_status()
                eyes_state = eyes_info.get("status", "ACTIVE")
                if eyes_state == "ACTIVE":
                    eyes_fmt = "[bold bright_green]ACTIVE (RAM/Local)[/bold bright_green]"
                elif eyes_state == "PAUSED":
                    eyes_fmt = "[bold yellow]PAUSED[/bold yellow]"
                else:
                    eyes_fmt = f"[bold cyan]{eyes_state}[/bold cyan]"
                cmd_table.add_row("NOVA Eyes:", eyes_fmt)

                layout["commands"].update(Panel(cmd_table, title="🖥️ Mac Control", border_style="magenta"))

                # F. Active System Recovery Alerts (Lower Right)
                active_alerts = DashboardStatsManager.get_active_alerts()
                resolved_alerts = DashboardStatsManager.get_resolved_alerts()

                if active_alerts:
                    alert_table = Table.grid(expand=True)
                    alert_table.add_column(style="bold red", width=11)
                    alert_table.add_column(style="bold")

                    top_alert = active_alerts[0]
                    alert_table.add_row("⚠ Alert:", top_alert.title)
                    alert_table.add_row("Subsystem:", top_alert.subsystem)
                    alert_table.add_row("Cause:", top_alert.details[:25] + ("..." if len(top_alert.details) > 25 else ""))
                    if top_alert.recovery_hint:
                        alert_table.add_row("Recovery:", top_alert.recovery_hint[:25])
                    if top_alert.retry_after:
                        alert_table.add_row("Retry in:", f"{int(top_alert.retry_after)}s")

                    layout["recovery"].update(Panel(alert_table, title=f"🏥 Alerts ({len(active_alerts)} Active)", border_style="red"))
                else:
                    rec_content = Table.grid(expand=True)
                    rec_content.add_column(style="bold", justify="center")
                    rec_content.add_row("[bold green]✓ NO SYSTEM ERRORS ACTIVE[/bold green]")
                    if resolved_alerts:
                        rec_content.add_row(f"[dim green]Latest: ✓ {resolved_alerts[0].title[:28]}[/dim green]")
                    else:
                        rec_content.add_row("[dim]All diagnostics healthy.[/dim]")

                    layout["recovery"].update(
                        Panel(
                            Align.center(rec_content),
                            title="🏥 System Recovery",
                            border_style="green",
                        )
                    )

            # -----------------------------------------------------------------
            # 4. Live User Activity Feed (Assistant Interaction Console)
            # -----------------------------------------------------------------
            if self.maximized:
                visible_capacity = max(10, term_lines - 6)
            else:
                visible_capacity = max(7, term_lines - 22)

            formatted_lines: list[Text] = []

            # A. Render Raw Debug Logs when requested
            if self.filter_mode in ("DEBUG", "RAW"):
                raw_logs = DashboardStatsManager.get_logs(search_query=self.search_query)
                for entry in raw_logs:
                    line = Text()
                    line.append(f"[{entry.time_str}] ", style="dim cyan")
                    if entry.level == "ERROR":
                        line.append("[ERROR]   ", style="bold red")
                    elif entry.level == "WARN":
                        line.append("[WARN]    ", style="bold yellow")
                    elif entry.level == "SUCCESS":
                        line.append("[SUCCESS] ", style="bold bright_green")
                    elif entry.level == "DEBUG":
                        line.append("[DEBUG]   ", style="dim magenta")
                    else:
                        line.append("[INFO]    ", style="bold green")

                    if entry.logger_name:
                        line.append(f"({entry.logger_name}) ", style="dim")
                    line.append(entry.message, style="white")
                    formatted_lines.append(line)

            # B. Render User Activity Feed (Default & Category Modes)
            else:
                interactions = DashboardStatsManager.get_activity_interactions(
                    filter_category=self.filter_mode, search_query=self.search_query
                )

                for idx, inter in enumerate(interactions):
                    # Separator between interaction blocks
                    if idx > 0:
                        sep_line = Text("─" * 60, style="dim")
                        formatted_lines.append(sep_line)

                    for step in inter.steps:
                        cat = step.category.upper()
                        time_prefix = f"{step.time_str}  "

                        # 1. YOU
                        if cat == "YOU":
                            header = Text()
                            header.append(time_prefix, style="dim cyan")
                            header.append("YOU", style="bold bright_cyan")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(f'"{step.text}"', style="bold white")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 1B. HEARD (Raw ASR Speech Transcript)
                        elif cat == "HEARD":
                            header = Text()
                            header.append(time_prefix, style="dim cyan")
                            header.append("HEARD", style="bold cyan")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(f'"{step.text}"', style="italic white")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 2. UNDERSTOOD
                        elif cat == "UNDERSTOOD":
                            header = Text()
                            header.append(time_prefix, style="dim magenta")
                            header.append("UNDERSTOOD", style="bold magenta")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(f"Intent: {step.text}\n", style="white")
                            if step.details:
                                for k, v in step.details.items():
                                    if k == "Steps" and isinstance(v, list):
                                        body.append("Multi-step task:\n", style="white")
                                        for s_idx, stp in enumerate(v):
                                            body.append(f"  {s_idx+1}. {stp}\n", style="dim white")
                                    else:
                                        body.append(f"{k}: {v}\n", style="dim white")
                            body.rstrip()
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 3. ACTION
                        elif cat == "ACTION":
                            header = Text()
                            header.append(time_prefix, style="dim yellow")
                            step_num = step.details.get("step_num") if step.details else None
                            total_steps = step.details.get("total_steps") if step.details else None
                            if step_num and total_steps:
                                header.append(f"ACTION {step_num}/{total_steps}", style="bold yellow")
                            else:
                                header.append("ACTION", style="bold yellow")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(f"{step.text}", style="yellow")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 3B. VERIFY (System & Action Verification)
                        elif cat == "VERIFY":
                            header = Text()
                            header.append(time_prefix, style="dim bright_blue")
                            header.append("VERIFY", style="bold bright_blue")
                            formatted_lines.append(header)

                            body = Text()
                            icon = "✓ " if step.success is not False else "✗ "
                            verify_color = "bold bright_green" if step.success is not False else "bold red"
                            body.append(f"{icon}{step.text}", style=verify_color)
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 4. NOVA
                        elif cat == "NOVA":
                            header = Text()
                            header.append(time_prefix, style="dim green")
                            header.append("NOVA", style="bold bright_green")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(f'"{step.text}"', style="bold green")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 5. RESULT
                        elif cat == "RESULT":
                            header = Text()
                            if step.success is False:
                                header.append(time_prefix, style="dim red")
                                header.append("RESULT", style="bold red")
                            else:
                                header.append(time_prefix, style="dim bright_green")
                                header.append("RESULT", style="bold bright_green")
                            formatted_lines.append(header)

                            body = Text()
                            res_text = step.text
                            if not res_text.startswith("✓") and not res_text.startswith("✗") and not res_text.startswith("●") and not res_text.startswith("⚠"):
                                icon = "✓ " if step.success is not False else "✗ "
                                res_text = f"{icon}{res_text}"
                            style_color = "bold bright_green" if step.success is not False else "bold red"
                            body.append(res_text, style=style_color)
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 6. ERROR
                        elif cat == "ERROR":
                            header = Text()
                            header.append(time_prefix, style="dim red")
                            header.append("ERROR", style="bold bright_red")
                            formatted_lines.append(header)

                            body = Text()
                            err_msg = step.text if step.text.startswith("⚠") or step.text.startswith("✗") else f"⚠ {step.text}"
                            body.append(err_msg, style="bold red")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

                        # 7. SYSTEM
                        elif cat == "SYSTEM":
                            header = Text()
                            header.append(time_prefix, style="dim")
                            header.append("SYSTEM", style="dim cyan")
                            formatted_lines.append(header)

                            body = Text()
                            body.append(step.text, style="dim")
                            formatted_lines.append(body)
                            formatted_lines.append(Text(""))

            total_rendered_lines = len(formatted_lines)

            # Viewport Slicing for Vertical Scrolling & Auto-scroll
            if total_rendered_lines == 0:
                feed_render_block = Text.from_markup(
                    "[dim]No interactions recorded yet. Speak or type a command to see live activity.[/dim]"
                )
            else:
                max_offset = max(0, total_rendered_lines - visible_capacity)
                current_offset = min(self.scroll_offset, max_offset)

                if self.auto_scroll or current_offset == 0:
                    start_idx = max(0, total_rendered_lines - visible_capacity)
                    end_idx = total_rendered_lines
                else:
                    end_idx = max(visible_capacity, total_rendered_lines - current_offset)
                    start_idx = max(0, end_idx - visible_capacity)

                visible_slice = formatted_lines[start_idx:end_idx]
                feed_render_block = Text()
                for line in visible_slice:
                    feed_render_block.append_text(line)
                    feed_render_block.append("\n")

            # Panel Title & Status
            state_val = stats.get("voice_state", "LISTENING")
            if state_val == "LISTENING":
                status_badge = "[bold cyan]● LISTENING[/bold cyan]"
            elif state_val == "THINKING":
                status_badge = "[bold yellow]🧠 THINKING[/bold yellow]"
            elif state_val == "SPEAKING":
                status_badge = "[bold green]🔊 SPEAKING[/bold green]"
            elif state_val == "INITIALIZE":
                status_badge = "[bold cyan]⚙ INITIALIZING[/bold cyan]"
            else:
                status_badge = "[bold dim]● IDLE[/bold dim]"

            filter_lbl = f"Filter: [{self.filter_mode}]"
            search_lbl = f" │ Search: '{self.search_query}'" if self.search_query else ""
            panel_title = f"📋 LIVE NOVA ACTIVITY FEED │ {filter_lbl}{search_lbl} │ {status_badge}"

            if self.auto_scroll:
                panel_subtitle = "[bold green]● LIVE AUTO-SCROLL ON[/bold green] [dim]│ /help for commands[/dim]"
            else:
                panel_subtitle = f"[bold yellow]⏸ AUTO-SCROLL PAUSED (+{self.scroll_offset} lines) │ /jump to resume[/bold yellow]"

            layout["activity_feed"].update(
                Panel(
                    feed_render_block,
                    title=panel_title,
                    subtitle=panel_subtitle,
                    border_style="cyan" if not self.maximized else "bright_blue",
                    padding=(0, 1),
                )
            )

            # -----------------------------------------------------------------
            # 5. Footer Status Bar
            # -----------------------------------------------------------------
            footer_text = Text(
                f"Current: {stats.get('current_task', 'Idle')} │ "
                f"Commands: /filter /clear /search /jump /scroll /max /copy /help",
                style="bold white",
                justify="center",
            )
            layout["footer"].update(footer_text)

            # -----------------------------------------------------------------
            # 6. Atomic Terminal Drawing
            # -----------------------------------------------------------------
            with self.console.capture() as capture:
                self.console.print(layout)
            canvas_str = capture.get()

            # Overwrite console cleanly using ANSI cursor home positioning
            sys.stdout.write("\033[s")  # Save cursor
            sys.stdout.write("\033[H")  # Home cursor
            for line in canvas_str.splitlines():
                sys.stdout.write(f"\033[K{line}\n")
            sys.stdout.write("\033[u")  # Restore cursor
            sys.stdout.flush()

        except Exception as e:
            logger.error("Error drawing terminal dashboard layout: %s", e)


