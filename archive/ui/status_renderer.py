"""Simple CLI inline progress spinners and diagnostic status indicators."""

from __future__ import annotations

import sys
import time

class StatusRenderer:
    """Provides simple CLI feedback widgets like spinning indicators."""

    @staticmethod
    def show_progress(message: str, duration: float = 0.4) -> None:
        """Render a temporary loading progress spinner on the terminal."""
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        steps = int(duration / 0.05)
        for i in range(steps):
            sys.stdout.write(f"\r\033[96m{spinner[i % len(spinner)]}\033[0m {message}...")
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write(f"\r\033[92m✓\033[0m {message} complete.\n")
        sys.stdout.flush()
