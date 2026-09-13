"""Subsystem orchestrator managing command parsing, confirmations, card rendering, and voice formatting."""

from __future__ import annotations

from core.logger import get_logger

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand
from mac_control.parser import CommandParser
from mac_control.router import CommandRouter

logger = get_logger(__name__)

class MacControlManager:
    """Core orchestrator for macOS Voice Control integration."""

    def __init__(self) -> None:
        self.parser = CommandParser()
        self.router = CommandRouter()
        self.pending_command: MacCommand | None = None
        self._is_enabled = True

    def health_check(self) -> bool:
        """Verify the mac control subsystem is healthy."""
        return self.parser is not None and self.router is not None

    def process_input(self, text: str) -> ExecutionResult | None:
        """Parse input, evaluate pending confirmations, execute matched commands.

        Returns ExecutionResult if a mac command is handled, otherwise None (fallback to LLM).
        """
        if not self._is_enabled:
            return None

        cleaned_text = text.lower().strip()

        # 1. Handle Awaiting Confirmation State
        if self.pending_command is not None:
            cmd = self.pending_command
            self.pending_command = None  # Clear state

            # Match confirmation yes / no variations
            if cleaned_text in ("yes", "ha", "haan", "sure", "do it", "confirm", "sahi hai", "haan kar do"):
                logger.info("Dangerous command confirmed: %s", cmd.action)
                res = self.router.route_and_execute(cmd)
                self._print_terminal_card(res)
                return res
            else:
                logger.info("Dangerous command cancelled or rejected: %s", cmd.action)
                cancel_res = ExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    message="Action cancelled, Boss.",
                    command_name=f"Cancel {cmd.category}",
                    category=cmd.category
                )
                self._print_terminal_card(cancel_res)
                return cancel_res

        # 2. Parse New Command
        cmd = self.parser.parse(text)
        if cmd is None:
            return None

        # 3. Intercept Dangerous Actions to Request Confirmation
        if cmd.is_dangerous:
            self.pending_command = cmd
            return ExecutionResult(
                status=ExecutionStatus.AWAITING_CONFIRMATION,
                message="Boss, are you sure?",
                command_name=f"Confirm {cmd.action.title()}",
                category=cmd.category
            )

        # 4. Route and Execute Immediately
        res = self.router.route_and_execute(cmd)
        self._print_terminal_card(res)

        try:
            from ui.health_checker import DashboardStatsManager
            target_val = cmd.args.get("app_name") or cmd.args.get("target") or cmd.args.get("query") or cmd.action
            DashboardStatsManager.record_mac_action(
                command_text=text,
                intent=f"{cmd.category.value}.{cmd.action}",
                target=str(target_val),
                status=res.status.value,
                latency_ms=res.execution_time_ms,
                result_message=res.message,
            )
        except Exception:
            pass

        return res

    def get_voice_response(self, res: ExecutionResult) -> str:
        """Map structured command results to natural spoken replies."""
        status = res.status
        action = res.command_name.lower()
        details = res.details

        if status == ExecutionStatus.AWAITING_CONFIRMATION:
            return "Boss, are you sure?"
        if status == ExecutionStatus.CANCELLED:
            return "Done Boss. Action cancelled."
        if status == ExecutionStatus.FAILED:
            return f"Sorry Boss. The command failed: {res.message}."
        if status == ExecutionStatus.PERMISSION_DENIED:
            return "Sorry Boss. System permissions are missing. Please grant Accessibility privileges."

        # Success voice mappings
        if "volume" in action:
            vol = details.get("volume", 50)
            if "unmute" in action:
                return "Done Boss. Audio output has been unmuted."
            elif "mute" in action:
                return "Done Boss. Audio output has been muted."
            elif "increase" in action:
                return f"Done Boss. Volume increased to {vol} percent."
            elif "decrease" in action:
                return f"Done Boss. Volume decreased to {vol} percent."
            return f"Done Boss. Volume set to {vol} percent."

        elif "brightness" in action:
            bri = details.get("brightness", 50)
            if "increase" in action:
                return f"Done Boss. Brightness increased to {bri} percent."
            elif "decrease" in action:
                return f"Done Boss. Brightness decreased to {bri} percent."
            return f"Done Boss. Brightness set to {bri} percent."

        elif "application" in action:
            app = details.get("app_name", "Application")
            if "open" in action:
                return f"Done Boss. {app} is open."
            elif "close" in action or "quit" in action:
                return f"Done Boss. {app} has been closed."
            elif "force" in action:
                return f"Done Boss. {app} was terminated."
            return f"Done Boss. {app} has been restarted."

        elif "website" in action:
            return "Done Boss. Website opened."

        elif "search" in action:
            q = details.get("query", "search")
            if "google" in action:
                return f"Done Boss. Searched Google for {q}."
            return f"Done Boss. Searched YouTube for {q}."

        elif "song" in action or "play" in action:
            song = details.get("song", "music")
            return f"Done Boss. Playing {song} on YouTube."

        elif "media" in action:
            if "pause" in action:
                return "Done Boss. Playback paused."
            elif "resume" in action:
                return "Done Boss. Playback resumed."
            return "Done Boss. Track changed."

        elif "folder" in action:
            fld = details.get("folder", "Finder")
            return f"Done Boss. {fld.title()} folder is open."

        elif "screenshot" in action:
            if "folder" in action:
                return "Done Boss. Screen shot folder is open."
            return "Done Boss. Screenshot captured."

        elif "clipboard" in action:
            if "copy" in action:
                return "Done Boss. Text copied."
            elif "paste" in action:
                return "Done Boss. Text pasted."
            return "Done Boss. Clipboard cleared."

        elif "wifi" in action:
            state = details.get("state", "changed")
            return f"Done Boss. WiFi has been turned {state}."

        elif "bluetooth" in action:
            state = details.get("state", "changed")
            return f"Done Boss. Bluetooth has been turned {state}."

        elif "sleep" in action:
            return "Done Boss. Sleep protocol initiated."
        elif "restart" in action:
            return "Done Boss. Executing system reboot."
        elif "shutdown" in action:
            return "Done Boss. Executing system shutdown."
        elif "lock" in action:
            return "Done Boss. Screen locked."
        elif "empty" in action:
            return "Done Boss. Trash emptied."

        return f"Done Boss. {res.message}."

    def _print_terminal_card(self, res: ExecutionResult) -> None:
        """Format and render the structured dashboard card on the stdout console."""
        # Clean terminal output cards
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🖥  MAC CONTROL")
        print(f"Command:\n{res.command_name}")
        print(f"Category:\n{res.category.value}")
        print(f"Status:\n{res.status.value}")
        print(f"Result:\n{res.message}")

        # Display current status detail conditionally
        if res.category == CommandCategory.VOLUME and "volume" in res.details:
            print(f"Current Volume:\n{res.details['volume']}%")
        elif res.category == CommandCategory.BRIGHTNESS and "brightness" in res.details:
            print(f"Current Brightness:\n{res.details['brightness']}%")
        elif res.category == CommandCategory.NETWORK and "ssid" in res.details and res.details["ssid"]:
            print(f"Network:\n{res.details['ssid']}")

        print(f"Execution Time:\n{res.execution_time_ms} ms")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
