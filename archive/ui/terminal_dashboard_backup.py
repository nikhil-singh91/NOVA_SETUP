"""NOVA Rich Terminal Operations Dashboard."""

from __future__ import annotations

import getpass
import shutil
import socket
import sys
import threading
import time
from typing import Any

from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import ProgressBar
from rich.table import Table
from rich.text import Text
from ui.health_checker import DashboardStatsManager, HealthChecker
from ui.startup_screen import StartupScreen

logger = get_logger(__name__)

class TerminalDashboard:
    """Coordinates and renders the rich real-time command operations center."""

    def __init__(self) -> None:
        self.checker = HealthChecker()
        self.console = Console()
        self._running = False
        self._updater_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start background update loops and event subscriptions."""
        with self._lock:
            if self._running:
                return
            self._running = True

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
            except Exception as e:
                logger.warning("Failed to subscribe dashboard to event bus: %s", e)

            self._updater_thread = threading.Thread(target=self._run_updater, daemon=True, name="nova-dashboard-updater")
            self._updater_thread.start()

    def stop(self) -> None:
        """Stop background diagnostic loops."""
        with self._lock:
            self._running = False
        if self._updater_thread:
            self._updater_thread.join(timeout=0.2)
            self._updater_thread = None

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
                DashboardStatsManager.update("current_task", f"Command completed: {cmd_name}")

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
        StartupScreen.show_boot_sequence()
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        self.checker.run_checks_async()
        self.draw_dashboard()
        self.start()

    def draw_dashboard(self) -> None:
        """Assemble grid panels and draw them in place using ANSI cursor overrides."""
        try:
            terminal_size = shutil.get_terminal_size((100, 30))
            width = min(110, max(80, terminal_size.columns))

            # Gathers system results
            results = self.checker.run_all_checks()
            stats = DashboardStatsManager.get_all()

            # Build Layout
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=4),
                Layout(name="body"),
                Layout(name="footer", size=1)
            )

            layout["body"].split_row(
                Layout(name="left_col", ratio=1),
                Layout(name="center_col", ratio=1),
                Layout(name="right_col", ratio=1)
            )

            layout["left_col"].split_column(
                Layout(name="voice", ratio=3),
                Layout(name="memory", ratio=2)
            )

            layout["center_col"].split_column(
                Layout(name="ai_providers", ratio=3),
                Layout(name="commands", ratio=2)
            )

            layout["right_col"].split_column(
                Layout(name="system", ratio=3),
                Layout(name="logs_and_errors", ratio=2)
            )

            # 1. Header Panel
            uptime_sec = int(time.time() - stats.get("session_start_time", time.time()))
            uptime_str = f"{uptime_sec // 60}m {uptime_sec % 60}s"
            header_table = Table.grid(expand=True)
            header_table.add_column(justify="left", style="bold cyan")
            header_table.add_column(justify="center", style="dim")
            header_table.add_column(justify="right", style="cyan")
            header_table.add_row(
                "🚀 NOVA OPERATIONS CONTROL CENTER",
                f"Uptime: {uptime_str} | Active User: {getpass.getuser()} | Host: {socket.gethostname()}",
                f"{time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            layout["header"].update(Panel(header_table, title="System Header", border_style="cyan"))

            # 2. Voice Panel (Left)
            voice_spec = results.get("voice", {})
            state_val = stats.get("voice_state", "LISTENING")

            # Waveform visual mock representation based on active state
            if state_val == "SPEAKING":
                wave_txt = "[bold green]▅▅▃▆▃▅▃▆▃▅▃▆▃▅[/bold green]"
            elif state_val == "LISTENING":
                wave_txt = "[bold cyan] ▃▂ ▂▃▂ ▂▃▂ ▂ [/bold cyan]"
            elif state_val == "THINKING":
                wave_txt = "[bold yellow] ░░░░░░░░░░░░░ [/bold yellow]"
            else:
                wave_txt = "[dim]--------------[/dim]"

            audio_level = stats.get("audio_level", 12)
            noise_level = stats.get("noise_level", 8)
            audio_bar = ProgressBar(total=100, completed=audio_level, width=15)

            # Determine dynamic microphone status
            mic_info = voice_spec.get("Microphone", "Checking...")
            if state_val == "SPEAKING":
                mic_status_str = f"{mic_info} [[bold red]MUTED[/]]"
            elif state_val == "LISTENING":
                mic_status_str = f"{mic_info} [[bold green]ON[/]]"
            else:
                mic_status_str = f"{mic_info} [[bold yellow]STANDBY[/]]"

            health_val = stats.get("thread_health", "HEALTHY")
            health_color = "green" if health_val == "HEALTHY" else "yellow"
            health_str = f"[bold {health_color}]{health_val}[/bold {health_color}]"

            voice_table = Table.grid(expand=True)
            voice_table.add_column(style="bold dim", width=16)
            voice_table.add_column(style="bold")
            voice_table.add_row("Microphone:", mic_status_str)
            voice_table.add_row("Speaker:", voice_spec.get("Speaker", "Checking..."))
            voice_table.add_row("VAD / Model:", f"Silero AI / Whisper {voice_spec.get('Speech Engine', 'Whisper')}")
            voice_table.add_row("Audio Pipeline:", "HPF + AGC + SNS + AEC")
            voice_table.add_row("Speech Prob:", stats.get("speech_confidence", "0%"))
            voice_table.add_row("Estimated SNR:", stats.get("estimated_snr", "0.0 dB"))
            voice_table.add_row("Mic/Rec State:", f"{stats.get('mic_state', 'STANDBY')} / {stats.get('recorder_state', 'STOPPED')}")
            voice_table.add_row("Whisper / Intent:", f"{stats.get('whisper_confidence', '0%')} / {stats.get('intent_confidence', '0%')}")
            voice_table.add_row("STT Latency:", stats.get("recognition_latency", "0.00s"))
            voice_table.add_row("Reject Reason:", stats.get("rejection_reason", "None"))
            voice_table.add_row("Thread Health:", health_str)
            voice_table.add_row("Recovery Count:", str(stats.get("recovery_count", 0)))
            voice_table.add_row("Audio State:", stats.get("current_audio_state", "No Speech Detected"))
            voice_table.add_row("Audio Level:", audio_bar)
            voice_table.add_row("Live Waveform:", wave_txt)
            voice_table.add_row("Last Transcript:", f"[italic green]\"{stats.get('last_transcript', 'None')}\"[/italic green]")

            layout["voice"].update(Panel(voice_table, title="Voice Subsystem", border_style="green" if state_val != "ERROR" else "red"))

            # 3. Memory Panel (Left Bottom)
            mem_spec = results.get("memory", {})
            mem_table = Table.grid(expand=True)
            mem_table.add_column(style="bold dim", width=16)
            mem_table.add_column(style="bold")
            mem_table.add_row("Backend Store:", mem_spec.get("Memory Backend", "JSON Database"))
            mem_table.add_row("Semantic DB:", "[bold green]ChromaDB[/bold green]" if mem_spec.get("Semantic Search") == "Enabled" else "[dim]Disabled[/dim]")
            mem_table.add_row("Stored Memories:", mem_spec.get("Stored Memories", "Checking..."))
            mem_table.add_row("Database Status:", f"[bold green]{mem_spec.get('Memory Status', 'Healthy')}[/bold green]")
            layout["memory"].update(Panel(mem_table, title="Memory Layer", border_style="blue"))

            # 4. AI Providers Panel (Center)
            prov_spec = results.get("providers", {})
            prov_table = Table(expand=True, box=None)
            prov_table.add_column("Provider", style="bold")
            prov_table.add_column("Status", justify="center")
            prov_table.add_column("Latency")

            for prov, key in [("Gemini", "Gemini"), ("Groq", "Groq"), ("OpenRouter", "OpenRouter"), ("Cerebras", "Cerebras")]:
                p_data = prov_spec.get(prov, {})
                status_lbl = p_data.get("status", "Checking...")
                if status_lbl == "Healthy":
                    status_fmt = "[bold green]Healthy[/bold green]"
                elif status_lbl == "Warning":
                    status_fmt = "[bold yellow]Warning[/bold yellow]"
                else:
                    status_fmt = "[bold red]Offline[/bold red]"
                prov_table.add_row(prov, status_fmt, p_data.get("latency", "N/A"))

            ai_summary_table = Table.grid(expand=True)
            ai_summary_table.add_column(style="bold dim", width=18)
            ai_summary_table.add_column(style="bold")
            ai_summary_table.add_row("Active Provider:", stats.get("active_provider", "Gemini"))
            ai_summary_table.add_row("Active Model:", stats.get("active_model", "gemini-2.5-flash"))
            ai_summary_table.add_row("Fallback Router:", "[bold green]Active[/bold green]")

            ai_layout = Layout()
            ai_layout.split_column(
                Layout(prov_table, ratio=2),
                Layout(ai_summary_table, ratio=1)
            )
            layout["ai_providers"].update(Panel(ai_layout, title="AI Providers", border_style="cyan"))

            # 5. Commands Panel (Center Bottom)
            cmd_table = Table.grid(expand=True)
            cmd_table.add_column(style="bold dim", width=16)
            cmd_table.add_column(style="bold")
            cmd_table.add_row("Last Command:", stats.get("last_command", "None"))
            cmd_table.add_row("Intent/Category:", stats.get("command_category", "None"))
            cmd_table.add_row("Execution Latency:", stats.get("command_execution_time", "0 ms"))
            cmd_table.add_row("Execution Status:", "[bold green]SUCCESS[/bold green]" if stats.get("command_status", "SUCCESS") == "SUCCESS" else "[bold red]FAILED[/bold red]")
            cmd_table.add_row("Action Result:", stats.get("command_result", "None"))
            layout["commands"].update(Panel(cmd_table, title="Mac Control Commands", border_style="magenta"))

            # 6. System Resource Panel (Right)
            perf_spec = results.get("performance", {})
            cpu_val_str = perf_spec.get("CPU", "0%").replace("%", "")
            ram_val_str = perf_spec.get("RAM", "0%").replace("%", "")
            try:
                cpu_val = float(cpu_val_str)
            except ValueError:
                cpu_val = 0.0
            try:
                ram_val = float(ram_val_str)
            except ValueError:
                ram_val = 0.0

            cpu_bar = ProgressBar(total=100, completed=cpu_val, width=15)
            ram_bar = ProgressBar(total=100, completed=ram_val, width=15)

            sys_table = Table.grid(expand=True)
            sys_table.add_column(style="bold dim", width=16)
            sys_table.add_column(style="bold")
            sys_table.add_row("CPU Utilization:", cpu_bar)
            sys_table.add_row("RAM Utilization:", ram_bar)
            sys_table.add_row("GPU hardware:", "Apple Silicon M2")
            sys_table.add_row("Python RSS memory:", perf_spec.get("Python Memory", "Checking..."))
            sys_table.add_row("Active Threads:", str(perf_spec.get("Threads", 0)))
            sys_table.add_row("Network status:", "[bold green]CONNECTED[/bold green]" if prov_spec.get("Internet", {}).get("status") == "Healthy" else "[bold red]OFFLINE[/bold red]")
            layout["system"].update(Panel(sys_table, title="System Performance Specs", border_style="yellow"))

            # 7. Stacked Logs & Errors (Right Bottom)
            # Create sub layout inside right bottom
            logs_errors_layout = Layout()
            logs_errors_layout.split_column(
                Layout(name="errors", size=6),
                Layout(name="logs")
            )

            # Setup Errors info
            if stats.get("errors_count", 0) > 0:
                err_table = Table.grid(expand=True)
                err_table.add_column(style="bold red", width=12)
                err_table.add_column(style="bold")
                err_table.add_row("Error Module:", stats.get("last_error_module", "Unknown"))
                err_table.add_row("Root Cause:", stats.get("last_error_reason", "None"))
                err_table.add_row("Auto Fix:", f"[bold green]{stats.get('last_error_recovery', 'None')}[/bold green]")
                logs_errors_layout["errors"].update(Panel(err_table, title="🏥 Active System Recovery Alerts", border_style="red"))
            else:
                logs_errors_layout["errors"].update(Panel(
                    Align.center("[bold green]✓ NO SYSTEM ERRORS ACTIVE[/bold green]\nDiagnostics state healthy."),
                    title="🏥 Active System Recovery Alerts", border_style="green"
                ))

            # Setup Logs info
            log_lines = DashboardStatsManager.get_logs()
            log_text = Text()
            for lvl, msg in log_lines:
                if lvl == "ERROR":
                    prefix = "[bold red][ERR][/bold red] "
                elif lvl == "WARNING":
                    prefix = "[bold yellow][WRN][/bold yellow] "
                elif lvl == "DEBUG":
                    prefix = "[dim][DBG][/dim] "
                else:
                    prefix = "[bold green][INF][/bold green] "
                log_text.append_text(Text.from_markup(f"{prefix}{msg}\n"))

            logs_errors_layout["logs"].update(Panel(log_text, title="Log Viewer Feed", border_style="dim"))
            layout["logs_and_errors"].update(logs_errors_layout)

            # 8. Footer Status
            state_display = state_val
            if state_val == "LISTENING":
                state_display = "🎤 Listening"
            elif state_val == "THINKING":
                state_display = "🧠 Thinking"
            elif state_val == "SPEAKING":
                state_display = "🔊 Speaking"
            elif state_val == "GREETING":
                state_display = "👋 Greeting"
            elif state_val == "INITIALIZE":
                state_display = "⚙️ Initializing"

            footer_text = Text(f"State: {state_display} | Target: {stats.get('current_task', 'None')}", style="bold white", justify="center")
            layout["footer"].update(footer_text)

            # 9. Render Layout to terminal using captured print & home coordinates
            with self.console.capture() as capture:
                self.console.print(layout)
            canvas_str = capture.get()

            # Overwrite console cleanly above prompt
            sys.stdout.write("\033[s") # Save cursor
            sys.stdout.write("\033[H") # Home cursor
            for line in canvas_str.splitlines():
                sys.stdout.write(f"\033[K{line}\n")
            sys.stdout.write("\033[u") # Restore cursor
            sys.stdout.flush()

        except Exception as e:
            logger.error("Error drawing terminal dashboard layout: %s", e)
