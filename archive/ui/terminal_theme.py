"""Styles and color theme configurations for the NOVA Terminal UI."""

class TerminalTheme:
    # ANSI escape colors
    CYAN = "\033[96m"
    DARK_CYAN = "\033[36m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    # Box-drawing Unicode characters
    TL = "┌"  # Top Left
    TR = "┐"  # Top Right
    BL = "└"  # Bottom Left
    BR = "┘"  # Bottom Right
    H = "─"   # Horizontal Line
    V = "│"   # Vertical Line
    T = "┬"   # Top Tee
    B = "┴"   # Bottom Tee
    L = "├"   # Left Tee
    R = "┤"   # Right Tee
    C = "┼"   # Cross/Center

    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        """Wrap text in terminal color sequences."""
        return f"{color}{text}{cls.RESET}"

    @classmethod
    def bold(cls, text: str) -> str:
        """Make text bold."""
        return f"{cls.BOLD}{text}{cls.RESET}"
