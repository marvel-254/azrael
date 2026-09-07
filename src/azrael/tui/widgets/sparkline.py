"""Sparkline widget wrapping a small block-character sparkline.

PLAN §6.3 says "TUI version uses Unicode Braille/Block for the arc fill".
For a sparkline of CPU% history, we use 8-step Block characters
(`▁▂▃▄▅▆▇█`) — enough resolution at small widths.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from textual.reactive import reactive
from textual.widgets import Static

if TYPE_CHECKING:
    from rich.visual import Visual


_BLOCKS: str = " ▁▂▃▄▅▆▇█"


def _block_for(value: float, lo: float, hi: float) -> str:
    if hi <= lo:
        return " "
    norm = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    idx = round(norm * (len(_BLOCKS) - 1))
    return _BLOCKS[idx]


class Sparkline(Static):
    """A single-line sparkline of the last N samples of an agent's CPU%."""

    DEFAULT_CSS = """
    Sparkline {
        height: 1;
        width: 1fr;
        padding: 0 1;
    }
    """

    samples: reactive[list[float]] = reactive(list, layout=False)
    maxlen: ClassVar[int] = 60

    def __init__(self, maxlen: int = 60, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._maxlen = maxlen
        self._data: list[float] = []

    def set_samples(self, samples: Sequence[float]) -> None:
        data = list(samples)[-self._maxlen :]
        self._data = data
        self.refresh()

    def render(self) -> Visual:
        from rich.text import Text

        return Text(self._data_to_str(), style="dim")

    def _data_to_str(self) -> str:
        if not self._data:
            return "─" * self._maxlen
        lo = min(self._data)
        hi = max(self._data)
        if hi == lo:
            hi = lo + 1.0
        return "".join(_block_for(v, lo, hi) for v in self._data)


__all__ = ["Sparkline"]
