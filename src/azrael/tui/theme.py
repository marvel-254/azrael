"""Design tokens for azrael (single source of truth for TUI + GUI).

Per PLAN §6.1 (palette) and §6.2 (hard rules). The dataclass is frozen so
the values cannot be mutated at runtime; the helpers produce ANSI 24-bit
escape sequences for plain-text rendering paths (TUI widgets and CLI
output). Textual widgets themselves read these via Rich markup.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    bg: str = "#1b1816"
    bezel: str = "#2a2522"
    bezel_edge: str = "#0e0c0b"
    tick: str = "#b9a892"
    needle: str = "#e8c178"
    needle_warn: str = "#e8893c"
    needle_crit: str = "#c63a3a"
    readout: str = "#f5ead2"
    accent: str = "#7fb88f"
    wire: str = "#3a322d"

    warn_at: float = 70.0
    crit_at: float = 90.0

    def needle_for(self, pct: float) -> str:
        """Pick needle color based on percent (color means something, per §6.2 rule 6)."""
        if pct >= self.crit_at:
            return self.needle_crit
        if pct >= self.warn_at:
            return self.needle_warn
        return self.needle

    @staticmethod
    def _rgb(hex_str: str) -> tuple[int, int, int]:
        h = hex_str.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"expected #rrggbb, got {hex_str!r}")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def hex_to_ansi_bg(self, hex_str: str) -> str:
        r, g, b = self._rgb(hex_str)
        return f"\033[48;2;{r};{g};{b}m"

    def hex_to_ansi_fg(self, hex_str: str) -> str:
        r, g, b = self._rgb(hex_str)
        return f"\033[38;2;{r};{g};{b}m"

    def ansi_reset(self) -> str:
        return "\033[0m"

    def fg_markup(self, hex_str: str) -> str:
        """Return a Rich-style hex tag for use in markup strings."""
        return hex_str


GLOBAL: Theme = Theme()


def hex_to_ansi_bg(hex_str: str) -> str:
    return GLOBAL.hex_to_ansi_bg(hex_str)


def hex_to_ansi_fg(hex_str: str) -> str:
    return GLOBAL.hex_to_ansi_fg(hex_str)


__all__ = ["GLOBAL", "Theme", "hex_to_ansi_bg", "hex_to_ansi_fg"]
