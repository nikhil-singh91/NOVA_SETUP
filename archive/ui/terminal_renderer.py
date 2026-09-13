"""Terminal column layout layout builder and screen rendering engine."""

from __future__ import annotations

from ui.terminal_widgets import visible_length


class TerminalRenderer:
    """Manages layout alignments, spacing, and multi-panel alignment grids."""

    @staticmethod
    def render_columns(col1: list[str], col2: list[str], gap: int = 4) -> list[str]:
        """Align two lists of string lines side-by-side with a spacing gap.

        Calculates correct padding to prevent alignment breakage from ANSI escape colors.
        """
        lines = []
        max_height = max(len(col1), len(col2))

        # Calculate maximum visual width for padding
        w1 = max((visible_length(line) for line in col1), default=0)
        w2 = max((visible_length(line) for line in col2), default=0)

        for i in range(max_height):
            l1 = col1[i] if i < len(col1) else ""
            l2 = col2[i] if i < len(col2) else ""

            # Pad column 1 to its max visible width
            p1 = w1 - visible_length(l1)
            # Pad column 2 to its max visible width
            p2 = w2 - visible_length(l2)

            lines.append(f"{l1}{' ' * p1}{' ' * gap}{l2}{' ' * p2}")

        return lines

    @staticmethod
    def center_text(text: str, width: int) -> str:
        """Center text relative to the screen width, ignoring ANSI color sequences."""
        vis_len = visible_length(text)
        padding = max(0, (width - vis_len) // 2)
        return f"{' ' * padding}{text}"
