"""macOS Centralized Screenshot Action Service for NOVA Desktop Assistant.

Provides reliable full-screen and interactive snapshot capabilities using native
macOS screencapture mechanisms with permissions preflight, directory creation,
timestamped formatting, environment tracking, and structured result representations.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScreenshotResult:
    """Structured response object returned by screenshot operations."""

    success: bool
    file_path: Path | None = None
    filename: str = ""
    error: str | None = None
    error_type: str | None = None  # e.g., "PERMISSION_DENIED", "EXECUTION_ERROR", "USER_CANCELLED"


class ScreenshotService:
    """Centralized service managing macOS screen captures, permissions, and storage."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir: Path = output_dir or (Path.home() / "Desktop" / "NOVA Screenshots").resolve()
        self._lock = threading.RLock()

    def check_permissions(self) -> tuple[bool, str]:
        """Check if screen recording/capture is permitted on macOS.

        Returns (is_permitted, status_message).
        """
        # 1. First attempt native macOS Quartz Preflight API
        try:
            import Quartz
            if hasattr(Quartz, "CGPreflightScreenCaptureAccess"):
                has_access = Quartz.CGPreflightScreenCaptureAccess()
                if not has_access:
                    return False, (
                        "macOS Screen Recording permission is missing. "
                        "Please grant Screen Recording permission for Terminal/Python in "
                        "System Settings -> Privacy & Security -> Screen Recording."
                    )
                return True, "Screen recording permissions verified."
        except Exception as exc:
            logger.debug("Quartz permission preflight note: %s", exc)

        # 2. Secondary probe using screencapture to a temporary file
        try:
            test_file = Path(f"/tmp/nova_sc_probe_{os.getpid()}.png")
            if test_file.exists():
                test_file.unlink()
            res = subprocess.run(
                ["screencapture", "-x", "-T", "0", str(test_file)],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if test_file.exists() and test_file.stat().st_size > 0:
                test_file.unlink()
                return True, "Screen capture permissions verified via probe."

            if res.returncode != 0 or "could not create image" in res.stderr.lower() or "denied" in res.stderr.lower():
                return False, (
                    "macOS Screen Recording permission is missing. "
                    "Please grant Screen Recording permission for Terminal/Python in "
                    "System Settings -> Privacy & Security -> Screen Recording."
                )
            return True, "Permission check passed."
        except Exception as exc:
            logger.warning("Screen capture permission probe error: %s", exc)
            return True, "Permission check proceed (fallback)."

    def _generate_unique_filepath(self, custom_filename: str | None = None) -> Path:
        """Generate a timestamped, collision-free file path inside the output directory."""
        if custom_filename:
            base_name = custom_filename if custom_filename.endswith(".png") else f"{custom_filename}.png"
            target = self.output_dir / base_name
            if not target.exists():
                return target

            stem = target.stem
            counter = 1
            while (self.output_dir / f"{stem}_{counter}.png").exists():
                counter += 1
            return self.output_dir / f"{stem}_{counter}.png"

        timestamp_str = datetime.now().strftime("%Y-%m-%d_at_%H.%M.%S")
        base_name = f"Screenshot_{timestamp_str}.png"
        target = self.output_dir / base_name
        if not target.exists():
            return target

        counter = 1
        while (self.output_dir / f"Screenshot_{timestamp_str}_{counter}.png").exists():
            counter += 1
        return self.output_dir / f"Screenshot_{timestamp_str}_{counter}.png"

    def capture_full_screen(
        self, custom_filename: str | None = None, silent: bool = True
    ) -> ScreenshotResult:
        """Capture the full primary screen and save to the default directory."""
        with self._lock:
            logger.info("Screenshot capture started (full screen)")

            # 1. Preflight permission check
            has_perm, perm_msg = self.check_permissions()
            if not has_perm:
                logger.error("Screenshot failure: %s", perm_msg)
                return ScreenshotResult(
                    success=False,
                    error=perm_msg,
                    error_type="PERMISSION_DENIED",
                )

            # 2. Ensure destination directory exists
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                err_msg = f"Failed to create screenshot folder '{self.output_dir}': {exc}"
                logger.error("Screenshot failure: %s", err_msg)
                return ScreenshotResult(
                    success=False,
                    error=err_msg,
                    error_type="EXECUTION_ERROR",
                )

            # 3. Generate file destination
            target_path = self._generate_unique_filepath(custom_filename)

            # 4. Invoke macOS native screencapture
            cmd = ["screencapture"]
            if silent:
                cmd.append("-x")
            cmd.append(str(target_path))

            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )

                if res.returncode != 0:
                    err_msg = f"screencapture exited with code {res.returncode}: {res.stderr.strip()}"
                    logger.error("Screenshot failure: %s", err_msg)
                    return ScreenshotResult(
                        success=False,
                        error=err_msg,
                        error_type="EXECUTION_ERROR",
                    )

                if not target_path.exists() or target_path.stat().st_size == 0:
                    # Clean up empty file if created
                    if target_path.exists():
                        target_path.unlink()
                    err_msg = "Screenshot capture produced an empty or missing image file."
                    logger.error("Screenshot failure: %s", err_msg)
                    return ScreenshotResult(
                        success=False,
                        error=err_msg,
                        error_type="EXECUTION_ERROR",
                    )

                # 5. Success - update environment observer context if available
                file_size = target_path.stat().st_size
                logger.info("Screenshot saved: '%s' (%d bytes)", target_path, file_size)

                try:
                    from core.environment import environment_observer, log_environment_debug
                    environment_observer.update_action_context(
                        action="SCREEN_CAPTURE",
                        created_path=target_path,
                    )
                    log_environment_debug("SCREEN_CAPTURE", target_path=str(target_path))
                except Exception as ctx_exc:
                    logger.debug("Environment observer context update note: %s", ctx_exc)

                return ScreenshotResult(
                    success=True,
                    file_path=target_path,
                    filename=target_path.name,
                )

            except Exception as exc:
                err_msg = f"Unexpected error during screenshot capture: {exc}"
                logger.error("Screenshot failure: %s", err_msg)
                return ScreenshotResult(
                    success=False,
                    error=err_msg,
                    error_type="EXECUTION_ERROR",
                )

    def capture_area(self, custom_filename: str | None = None) -> ScreenshotResult:
        """Interactively capture a user-selected area on the screen."""
        with self._lock:
            logger.info("Screenshot capture started (interactive area)")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            target_path = self._generate_unique_filepath(custom_filename)

            try:
                subprocess.run(["screencapture", "-i", str(target_path)], capture_output=True, text=True)
                if target_path.exists() and target_path.stat().st_size > 0:
                    logger.info("Screenshot saved: '%s'", target_path)
                    return ScreenshotResult(success=True, file_path=target_path, filename=target_path.name)
                else:
                    logger.info("Area screenshot cancelled by user.")
                    return ScreenshotResult(success=False, error="Area selection cancelled", error_type="USER_CANCELLED")
            except Exception as exc:
                err_msg = f"Area screenshot failed: {exc}"
                logger.error("Screenshot failure: %s", err_msg)
                return ScreenshotResult(success=False, error=err_msg, error_type="EXECUTION_ERROR")

    def capture_window(self, custom_filename: str | None = None) -> ScreenshotResult:
        """Interactively capture a user-selected application window."""
        with self._lock:
            logger.info("Screenshot capture started (interactive window)")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            target_path = self._generate_unique_filepath(custom_filename)

            try:
                subprocess.run(["screencapture", "-w", str(target_path)], capture_output=True, text=True)
                if target_path.exists() and target_path.stat().st_size > 0:
                    logger.info("Screenshot saved: '%s'", target_path)
                    return ScreenshotResult(success=True, file_path=target_path, filename=target_path.name)
                else:
                    logger.info("Window screenshot cancelled by user.")
                    return ScreenshotResult(success=False, error="Window selection cancelled", error_type="USER_CANCELLED")
            except Exception as exc:
                err_msg = f"Window screenshot failed: {exc}"
                logger.error("Screenshot failure: %s", err_msg)
                return ScreenshotResult(success=False, error=err_msg, error_type="EXECUTION_ERROR")

    def open_screenshot_folder(self) -> tuple[bool, str]:
        """Open the default screenshots directory in macOS Finder."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(self.output_dir)], check=True)
            return True, f"Opened {self.output_dir}"
        except Exception as exc:
            return False, f"Failed to open screenshot directory: {exc}"


# Global singleton instance
screenshot_service = ScreenshotService()
