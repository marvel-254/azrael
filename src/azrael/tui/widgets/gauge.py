"""Text-mode analog gauge.

Per PLAN §9 + §6.3, the TUI version uses Unicode Block/Arc characters.
We keep it intentionally simple: a one-row arc with a needle `▲` whose
position is driven by `value` (0..100 or 0..300 for over-quota CPU%).
The label below the arc shows `title` and the live percentage in the
needle color (which encodes warn / crit per §6.2 rule 6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.reactive import reactive
from textual.widgets import Static

from azrael.tui.theme import GLOBAL, Theme

if TYPE_CHECKING:
    from rich.visual import Visual


class AnalogGauge(Static):
    """A small text-mode gauge. Renders as three stacked rows."""

    DEFAULT_CSS = """
    AnalogGauge {
        height: 3;
        width: auto;
        border: round $wire;
        padding: 0 1;
    }
    """

    value: reactive[float] = reactive(0.0)
    title: reactive[str] = reactive("")

    def __init__(
        self,
        title: str = "",
        *,
        width: int = 22,
        warn_at: float | None = None,
        crit_at: float | None = None,
        theme: Theme = GLOBAL,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._width = max(8, width)
        self._warn_at = theme.warn_at if warn_at is None else warn_at
        self._crit_at = theme.crit_at if crit_at is None else crit_at
        self._theme = theme
        self.title = title

    def set_value(self, value: float) -> None:
        self.value = float(value)

    def _needle_color(self, pct: float) -> str:
        if pct >= self._crit_at:
            return self._theme.needle_crit
        if pct >= self._warn_at:
            return self._theme.needle_warn
        return self._theme.needle

    def render(self) -> Visual:
        from rich.text import Text

        return Text.from_markup(self._render_str())

    def _render_str(self) -> str:
        pct = max(0.0, min(self.value, 100.0))
        width = self._width
        arc = "╭" + "─" * (width - 2) + "╮"
        # Needle position: 0 -> 1 (just after left corner), 100 -> width-2
        inner = width - 2
        pos = 1 + round(pct / 100.0 * max(inner - 1, 1))
        pos = max(1, min(pos, inner))
        middle = " " * (pos - 1) + "▲" + " " * (inner - pos)
        middle_row = "│" + middle + "│"
        color = self._needle_color(pct)
        label = f"{self.title} {pct:5.1f}%"
        bottom = "╰" + "─" * (width - 2) + "╯"
        return f"[{color}]{arc}\n{middle_row}\n{label}[/] {bottom}"

    def watch_value(self) -> None:
        self.refresh()

    def watch_title(self) -> None:
        self.refresh()


__all__ = ["AnalogGauge"]
