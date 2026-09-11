"""NOVA Self-Diagnostics and Doctor Suite."""

from __future__ import annotations

import os
import sys
import shutil
import platform
import socket
import threading
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

class Doctor:
    """NOVA System Self-Diagnostics Suite."""

    def __init__(self) -> None:
        self.console = Console()
        self.issues: list[dict[str, str]] = []

    def run(self) -> int:
        """Run all diagnostic checks and output a styled diagnostics report."""
        self.console.print(Panel.fit(
            "[bold cyan]NOVA AI OPERATING SYSTEM - SELF DIAGNOSTICS SUITE[/]",
            border_style="cyan"
        ))

        table = Table(title="Diagnostic Checks Status", expand=True)
        table.add_column("Category", style="cyan", width=20)
        table.add_column("Diagnostic Target", style="bold", width=30)
        table.add_column("Status", width=15, justify="center")
        table.add_column("Details", style="dim")

        # 1. System & Resources
        self._check_python(table)
        self._check_system_resources(table)
        
        # 2. Dependencies
        self._check_dependencies(table)
        
        # 3. Environment & Config
        self._check_env_keys(table)
        
        # 4. Hardware Audio
        self._check_audio_hardware(table)
        
        # 5. AI Providers & Network
        self._check_ai_endpoints(table)
        
        # 6. Database & Memory
        self._check_databases(table)
        
        # 7. OS Permissions
        self._check_os_permissions(table)

        self.console.print(table)
        self.console.print()

        # Print Auto-Fix recommendations if issues exist
        if self.issues:
            self.console.print(Panel(
                "[bold yellow]⚠️  AUTO-FIX RECOMMENDATIONS[/]\n\n" + 
                "\n\n".join(
                    f"[bold red]✗ {issue['target']}[/]\n"
                    f"  [bold]Problem:[/bold] {issue['problem']}\n"
                    f"  [bold green]Suggested Fix Command:[/] {issue['fix']}"
                    for issue in self.issues
                ),
                border_style="yellow",
                title="System Fixes Guide"
            ))
            return 1
        else:
            self.console.print(Panel(
                "[bold green]✓ ALL SYSTEMS GO![/] NOVA has passed all operations checks.",
                border_style="green"
            ))
            return 0

    def _add_result(self, table: Table, category: str, target: str, status: str, details: str, problem: str | None = None, fix: str | None = None) -> None:
        if status == "PASS":
            status_text = "[bold green]PASS[/]"
        elif status == "WARNING":
            status_text = "[bold yellow]WARNING[/]"
            if problem and fix:
                self.issues.append({"target": target, "problem": problem, "fix": fix})
        else:
            status_text = "[bold red]FAIL[/]"
            if problem and fix:
                self.issues.append({"target": target, "problem": problem, "fix": fix})
                
        table.add_row(category, target, status_text, details)

    def _check_python(self, table: Table) -> None:
        py_ver = platform.python_version()
        if sys.version_info >= (3, 10):
            self._add_result(table, "Environment", "Python Version", "PASS", f"Active: {py_ver} (>= 3.10 required)")
        else:
            self._add_result(
                table, "Environment", "Python Version", "FAIL", f"Active: {py_ver}",
                "Python version is out of date.", "Upgrade to Python 3.10+ using: pyenv install 3.12 && pyenv global 3.12"
            )

    def _check_system_resources(self, table: Table) -> None:
        # Disk check
        try:
            total, used, free = shutil.disk_usage(".")
            free_gb = free / (1024 ** 3)
            if free_gb > 2.0:
                self._add_result(table, "Resources", "Disk Space", "PASS", f"{free_gb:.1f} GB Free space")
            else:
                self._add_result(
                    table, "Resources", "Disk Space", "WARNING", f"{free_gb:.1f} GB Free",
                    "Low disk space.", "Free up disk space or clean temporary cache files."
                )
        except Exception as e:
            self._add_result(table, "Resources", "Disk Space", "WARNING", f"Error: {e}")

        # RAM / Process memory
        try:
            import psutil
            mem = psutil.virtual_memory()
            mem_free_gb = mem.available / (1024 ** 3)
            if mem.percent < 90:
                self._add_result(table, "Resources", "RAM Availability", "PASS", f"{mem.percent}% used ({mem_free_gb:.1f} GB free)")
            else:
                self._add_result(
                    table, "Resources", "RAM Availability", "WARNING", f"{mem.percent}% used",
                    "RAM resources are heavily occupied.", "Close resource-heavy running processes."
                )
        except Exception:
            pass

    def _check_dependencies(self, table: Table) -> None:
        deps = [
            ("pyaudio", "PyAudio", "PortAudio python library bindings", "pip install pyaudio"),
            ("torch", "PyTorch", "Deep Learning framework engine", "pip install torch torchvision torchaudio"),
            ("pygame", "Pygame", "Audio mixer playback framework", "pip install pygame"),
            ("rich", "Rich", "Terminal formatted layout rendering", "pip install rich"),
            ("faster_whisper", "Faster Whisper", "Localized speech recognition models", "pip install faster-whisper")
        ]

        for mod_name, disp_name, desc, install_cmd in deps:
            try:
                __import__(mod_name)
                self._add_result(table, "Dependencies", disp_name, "PASS", f"Imported successfully ({desc})")
            except ImportError:
                self._add_result(
                    table, "Dependencies", disp_name, "FAIL", "Missing package",
                    f"The required package '{disp_name}' is not installed.", install_cmd
                )

        # check ffmpeg binary
        if shutil.which("ffmpeg"):
            self._add_result(table, "Dependencies", "FFmpeg Binary", "PASS", "Executable found in PATH")
        else:
            self._add_result(
                table, "Dependencies", "FFmpeg Binary", "FAIL", "Command not found",
                "FFmpeg is missing. Whisper model transcribing requires it to decode audio formats.",
                "brew install ffmpeg"
            )

    def _check_env_keys(self, table: Table) -> None:
        from core.paths import project_root
        env_file = project_root() / ".env"
        if env_file.exists():
            self._add_result(table, "Configuration", "Environment File", "PASS", "Located active .env file")
        else:
            self._add_result(
                table, "Configuration", "Environment File", "WARNING", "Missing .env",
                "The configuration .env file is missing from project directory root.",
                "cp .env.example .env && nano .env"
            )

        # Check critical keys
        keys_to_check = {
            "GEMINI_API_KEY": "Gemini Provider",
            "GROQ_API_KEY": "Groq Provider",
            "OPENROUTER_API_KEY": "OpenRouter",
            "CEREBRAS_API_KEY": "Cerebras"
        }
        for key, name in keys_to_check.items():
            val = os.environ.get(key) or ""
            if val.strip() and val != "mock_key" and not val.startswith("PASTE_"):
                self._add_result(table, "API Keys", name, "PASS", "Key set (non-empty)")
            else:
                self._add_result(
                    table, "API Keys", name, "WARNING", "Missing/empty Key",
                    f"API authorization Key for {name} ({key}) is empty or missing.",
                    f"Open your .env file and configure: {key}=your_actual_api_key"
                )

    def _check_audio_hardware(self, table: Table) -> None:
        p = None
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            
            try:
                info = p.get_default_input_device_info()
                self._add_result(table, "Audio Node", "Default Microphone", "PASS", f"{info.get('name')} (Index={info.get('index')})")
            except Exception as e:
                self._add_result(
                    table, "Audio Node", "Default Microphone", "FAIL", "No default input device",
                    "No microphone found or PortAudio stream is closed.",
                    "Verify audio device connection or open macOS System Settings -> Sound -> Input."
                )

            try:
                info = p.get_default_output_device_info()
                self._add_result(table, "Audio Node", "Default Speaker", "PASS", f"{info.get('name')} (Index={info.get('index')})")
            except Exception as e:
                self._add_result(
                    table, "Audio Node", "Default Speaker", "FAIL", "No default output device",
                    "No speaker found.",
                    "Verify audio output device connection or open macOS System Settings -> Sound -> Output."
                )
                
        except Exception as e:
            self._add_result(table, "Audio Node", "PortAudio Engine", "FAIL", str(e))
        finally:
            if p is not None:
                p.terminate()

    def _check_ai_endpoints(self, table: Table) -> None:
        # Check internet
        internet = False
        try:
            socket.setdefaulttimeout(1.5)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 53))
            s.close()
            self._add_result(table, "Connectivity", "Internet Connection", "PASS", "Ping to 8.8.8.8:53 succeeded")
            internet = True
        except Exception:
            self._add_result(
                table, "Connectivity", "Internet Connection", "FAIL", "Offline",
                "No internet connection found or port 53 is blocked.",
                "Verify network interface adapters, router connection, or DNS configurations."
            )

        if not internet:
            return

        # Fast Provider reachability handshake checks
        provider_endpoints = [
            ("generativelanguage.googleapis.com", "Gemini Endpoint"),
            ("api.groq.com", "Groq Endpoint"),
            ("openrouter.ai", "OpenRouter Endpoint"),
            ("api.cerebras.ai", "Cerebras Endpoint")
        ]

        for host, label in provider_endpoints:
            try:
                socket.setdefaulttimeout(2.0)
                ip = socket.gethostbyname(host)
                # Test connection to port 443
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, 443))
                s.close()
                self._add_result(table, "Connectivity", label, "PASS", f"Connection test to {host}:443 succeeded")
            except Exception as e:
                self._add_result(
                    table, "Connectivity", label, "WARNING", "Port 443 blocked / Connection failed",
                    f"Unable to reach {label} API gateway.",
                    f"Verify API routing rules, proxy status, or run: curl -I https://{host}/"
                )

    def _check_databases(self, table: Table) -> None:
        # Memory DB
        from core.paths import MEMORY_DIR
        store_file = MEMORY_DIR / "memory_store.json"
        if store_file.exists():
            self._add_result(table, "Databases", "JSON Memory Store", "PASS", f"Located store at {store_file.name}")
        else:
            self._add_result(
                table, "Databases", "JSON Memory Store", "WARNING", "File missing",
                "JSON memory store is missing (will auto create on first run).",
                "No action required - system initializes a fresh database at runtime."
            )

        # ChromaDB / Vector database query check
        has_vector_db = False
        try:
            from core.registry import registry
            if registry.exists("vector_store"):
                vs = registry.get("vector_store")
                if vs.health_check():
                    self._add_result(table, "Databases", "Vector DB (Chroma)", "PASS", "Active and queryable")
                    has_vector_db = True
            
            if not has_vector_db:
                # Attempt to verify chroma package import
                import chromadb
                self._add_result(table, "Databases", "Vector DB (Chroma)", "WARNING", "Package imported, service not loaded")
        except Exception as e:
            self._add_result(
                table, "Databases", "Vector DB (Chroma)", "WARNING", f"Offline: {e}",
                "Vector database query check failed.",
                "Ensure chromadb is installed and data directory permissions are healthy."
            )

    def _check_os_permissions(self, table: Table) -> None:
        # Check system permissions on macOS
        if platform.system() != "Darwin":
            self._add_result(table, "OS Permissions", "Mac System Settings", "PASS", "Bypassed (Not running on macOS)")
            return

        # Microphone permission test
        # We can't query macOS mic permissions easily via terminal API without UI cues,
        # but default device checks already verify if stream opening works.
        # Accessibility check using osascript to see if Terminal client has automation control
        import subprocess
        try:
            proc = subprocess.run(
                ["osascript", "-e", "tell application \"System Events\" to get name of current user"],
                capture_output=True, text=True, timeout=2.0
            )
            if proc.returncode == 0:
                self._add_result(table, "OS Permissions", "System Automation", "PASS", "Granted (AppleScript execution enabled)")
            else:
                self._add_result(
                    table, "OS Permissions", "System Automation", "WARNING", "Automation blocked",
                    "Terminal has no system automation control permission.",
                    "Open System Settings -> Privacy & Security -> Automation, and enable System Events for Python/Terminal."
                )
        except Exception:
            self._add_result(table, "OS Permissions", "System Automation", "WARNING", "Could not check automation")
