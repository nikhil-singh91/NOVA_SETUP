"""macOS Screen Recording Service and Manager for NOVA.

Provides bounded, verifiable screen recording via native macOS mechanisms,
managing active recording state, permissions checking, and verified output files.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.environment import environment_observer, log_environment_debug
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScreenRecordingResult:
    """Structured result returned by ScreenRecordingManager operations."""
    success: bool
    status: str
    file_path: Path | None = None
    spoken_response: str = ""
    error: str | None = None
    recording_active: bool = False
    message: str = ""

    def __iter__(self):
        """Enable backward-compatible tuple unpacking: (success, message, [file_path])."""
        yield self.success
        yield self.spoken_response or self.message
        yield self.file_path


class ScreenRecordingManager:
    """Manages start, state tracking, clean termination, and output verification of screen recordings."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir: Path = output_dir or (Path.home() / "Desktop" / "NOVA Recordings").resolve()
        self._proc: subprocess.Popen[Any] | None = None
        self._active_file: Path | None = None
        self._start_time: float | None = None
        self._lock = threading.RLock()

    def check_permissions(self) -> tuple[bool, str]:
        """Check if screen recording is permitted on macOS."""
        try:
            test_file = Path("/tmp/nova_rec_probe.png")
            if test_file.exists():
                test_file.unlink()
            res = subprocess.run(
                ["screencapture", "-x", str(test_file)],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if test_file.exists() and test_file.stat().st_size > 0:
                test_file.unlink()
                return True, "Screen recording permissions verified."

            if res.returncode != 0 or "could not create image" in res.stderr.lower():
                return False, (
                    "macOS Screen Recording permission is missing. "
                    "Please grant permission to Terminal or Python in System Settings -> Privacy & Security -> Screen Recording."
                )
            return True, "Permission check passed."
        except Exception as exc:
            logger.warning("Permission probe exception: %s", exc)
            return True, "Permission probe note (proceeding)."

    def start_recording(self, custom_filename: str | None = None) -> ScreenRecordingResult:
        """Start a new macOS screen recording."""
        with self._lock:
            if self.is_recording():
                msg = "Screen recording is already running."
                logger.info("Screen recording start requested but already active (PID=%s)", self._proc.pid if self._proc else "unknown")
                return ScreenRecordingResult(
                    success=False,
                    status="ALREADY_RUNNING",
                    file_path=self._active_file,
                    spoken_response=msg,
                    message=msg,
                    recording_active=True,
                )

            # Check permissions
            perm_ok, perm_msg = self.check_permissions()
            if not perm_ok:
                logger.warning("Screen recording start failed: %s", perm_msg)
                return ScreenRecordingResult(
                    success=False,
                    status="PERMISSION_DENIED",
                    error=perm_msg,
                    spoken_response=perm_msg,
                    message=perm_msg,
                    recording_active=False,
                )

            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.error("Failed to create output directory %s: %s", self.output_dir, exc)

            # Formulate timestamped output file
            if custom_filename:
                fname = custom_filename if (custom_filename.endswith(".mp4") or custom_filename.endswith(".mov")) else f"{custom_filename}.mp4"
            else:
                timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                fname = f"NOVA_Screen_{timestamp_str}.mp4"

            target_path = (self.output_dir / fname).resolve()
            self._active_file = target_path

            log_environment_debug("START_SCREEN_RECORDING", target_path=str(target_path))
            logger.info("Starting screen recording backend: screencapture -v -> %s", target_path)

            try:
                # screencapture -v records video to target_path until interrupted
                self._proc = subprocess.Popen(
                    ["screencapture", "-v", str(target_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,  # Run in distinct process group for clean signal dispatch
                )
                self._start_time = time.monotonic()

                # Update global environment context
                ctx = environment_observer.get_context()
                ctx.active_screen_recording = True
                ctx.recording_file_path = str(target_path)
                environment_observer.update_action_context(
                    action="START_SCREEN_RECORDING",
                    created_path=target_path,
                )

                spoken = "Screen recording started."
                logger.info("Screen recording started successfully: PID=%d, File=%s", self._proc.pid, target_path)
                return ScreenRecordingResult(
                    success=True,
                    status="RECORDING_STARTED",
                    file_path=target_path,
                    spoken_response=spoken,
                    message=f"Screen recording started (PID={self._proc.pid}). Saving to {fname}.",
                    recording_active=True,
                )

            except Exception as exc:
                logger.error("Failed to start screen recording process: %s", exc, exc_info=True)
                self._proc = None
                self._active_file = None
                self._start_time = None
                return ScreenRecordingResult(
                    success=False,
                    status="FAILED_TO_START",
                    error=str(exc),
                    spoken_response=f"Failed to start screen recording: {exc}",
                    message=f"Failed to start screen recording: {exc}",
                    recording_active=False,
                )

    def stop_recording(self) -> ScreenRecordingResult:
        """Stop the active screen recording and verify the saved output file."""
        with self._lock:
            proc = self._proc
            active_file = self._active_file

            if proc is None or proc.poll() is not None:
                # Reset stale state if any
                self._proc = None
                self._active_file = None
                ctx = environment_observer.get_context()
                ctx.active_screen_recording = False
                ctx.recording_file_path = None
                spoken = "There is no active screen recording."
                logger.info("Screen recording stop requested, but no active recording was running.")
                return ScreenRecordingResult(
                    success=False,
                    status="NOT_RECORDING",
                    spoken_response=spoken,
                    message=spoken,
                    recording_active=False,
                )

            log_environment_debug("STOP_SCREEN_RECORDING", pid=proc.pid, file=str(active_file))
            logger.info("Stopping screen recording PID=%d...", proc.pid)

            # Send SIGINT to the process group so screencapture finalizes the container cleanly
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            except Exception as exc:
                logger.debug("killpg SIGINT note: %s; fallback to proc.send_signal", exc)
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass

            # Wait up to 5 seconds for screencapture to flush video frames
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                logger.warning("screencapture did not exit on SIGINT; sending SIGTERM.")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=2.0)
                except Exception:
                    pass

            self._proc = None
            self._start_time = None

            # Reset environment context
            ctx = environment_observer.get_context()
            ctx.active_screen_recording = False
            ctx.recording_file_path = None

            # Verify output file
            if active_file and active_file.exists():
                file_size = active_file.stat().st_size
                if file_size > 0:
                    size_mb = file_size / (1024 * 1024)
                    spoken = "Screen recording stopped and saved to your Desktop."
                    logger.info("Screen recording verified: %s (%.2f MB)", active_file, size_mb)
                    environment_observer.update_action_context(
                        action="STOP_SCREEN_RECORDING",
                        created_path=active_file,
                    )
                    return ScreenRecordingResult(
                        success=True,
                        status="RECORDING_SAVED",
                        file_path=active_file,
                        spoken_response=spoken,
                        message=f"Screen recording saved ({size_mb:.1f} MB) at {active_file.name}.",
                        recording_active=False,
                    )

            return ScreenRecordingResult(
                success=False,
                status="NO_OUTPUT_FILE",
                file_path=active_file,
                spoken_response="Screen recording stopped, but no output video was generated.",
                message="Screen recording stopped, but no output video was generated.",
                error="No video file produced",
                recording_active=False,
            )

    def is_recording(self) -> bool:
        """Check if a screen recording process is actively running."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True
            return False

    def cancel_recording(self) -> bool:
        """Cancel and clean up any ongoing screen recording without keeping the file."""
        with self._lock:
            if not self.is_recording():
                return False
            res = self.stop_recording()
            if res.file_path and res.file_path.exists():
                try:
                    res.file_path.unlink()
                except Exception:
                    pass
            return True


# Global singleton manager and alias
screen_recording_manager = ScreenRecordingManager()
ScreenRecordingService = ScreenRecordingManager
