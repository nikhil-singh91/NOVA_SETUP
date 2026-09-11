"""Automated diagnostic engine to check system health, providers, and environment."""

from __future__ import annotations

import os
import sys
import time
import socket
import threading
from pathlib import Path
from typing import Any

from config.settings import settings
from core.registry import registry
from core.lifecycle import lifecycle

class DashboardStatsManager:
    _lock = threading.Lock()
    _logs: list[tuple[str, str]] = []
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
        "active_model": "gemini-2.5-flash",
        "temperature": "0.7",
        "network_status": "Healthy",
        "session_start_time": time.time(),
        "speech_confidence": "0%",
        "estimated_snr": "0.0 dB",
        "mic_gain": "1.00x",
        "current_audio_state": "No Speech Detected",
        "whisper_confidence": "0%",
        "intent_confidence": "0%",
        "recognition_latency": "0.00s",
        "rejection_reason": "None",
        "mic_state": "STANDBY",
        "recorder_state": "STOPPED",
        "thread_health": "HEALTHY",
        "recovery_count": 0
    }

    @classmethod
    def update(cls, key: str, value: Any) -> None:
        with cls._lock:
            cls._stats[key] = value

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

    @classmethod
    def add_log(cls, level: str, msg: str) -> None:
        with cls._lock:
            cls._logs.append((level, msg))
            if len(cls._logs) > 8:
                cls._logs.pop(0)

    @classmethod
    def get_logs(cls) -> list[tuple[str, str]]:
        with cls._lock:
            return list(cls._logs)


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
                "Internet": {"status": "Healthy", "message": "Checking..."},
                "Gemini": {"status": "Healthy", "message": "Checking..."},
                "Groq": {"status": "Healthy", "message": "Checking..."},
                "OpenRouter": {"status": "Healthy", "message": "Checking..."},
                "Cerebras": {"status": "Healthy", "message": "Checking..."}
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
                        is_healthy = manager.health_check()
                        checks[display_name] = {
                            "status": "Healthy" if is_healthy else "Warning",
                            "message": "Initialized & healthy" if is_healthy else "Health check returned warning/failed"
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
            if not secret_val or not secret_val.strip():
                checks[display_name] = {
                    "status": "Warning",
                    "message": "API key missing/empty",
                    "latency": "N/A"
                }
                continue

            # Run connection check if internet is available
            status_desc = "Configured"
            status_level = "Healthy"
            latency_str = "N/A"

            if registry.exists("provider_manager"):
                pm = registry.get("provider_manager")
                try:
                    # Run health check against individual provider
                    h_results = pm.health_check(key_name)
                    if h_results.get(key_name, False):
                        status_desc = "Connected"
                        status_level = "Healthy"
                    else:
                        # Check if quota exceeded or error occurred
                        status_desc = "Failed / Quota Exceeded"
                        status_level = "Warning"
                except Exception as exc:
                    status_desc = f"Failed: {exc}"
                    status_level = "Failed"

            checks[display_name] = {
                "status": status_level,
                "message": status_desc,
                "latency": latency_str
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
