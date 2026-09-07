"""AgentStrip — top strip of detected agents.

A `textual.containers.Horizontal` of one chip per detected agent. The App
holds the focused index; pressing `←` / `→` rotates it. We expose a
`set_agents(...)` that rebuilds the strip on each tick.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from azrael.metrics.types import Agent
from azrael.tui.theme import GLOBAL

if TYPE_CHECKING:
    from rich.visual import Visual


@dataclass(frozen=True)
class _ChipData:
    key: str
    label: str
    cpu_pct: float
    mem_text: str


_BAR_CHARS: str = "▁▂▃▄▅▆▇"


def _cpu_bar(pct: float, width: int = 8) -> str:
    pct = max(0.0, min(pct, 100.0))
    filled = round(pct / 100.0 * width)
    return "".join(_BAR_CHARS[-1] for _ in range(filled)) + "".join(
        "▁" for _ in range(width - filled)
    )


def _fmt_bytes(n: int) -> str:
    # binary units by default per PLAN §6 + config default
    f = float(n)
    for unit in ("B", "K", "M", "G", "T"):
        if f < 1024 or unit == "T":
            if unit == "B":
                return f"{int(f)}B"
            return f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}T"


class _AgentChip(Static):
    DEFAULT_CSS = """
    _AgentChip {
        height: 1;
        width: auto;
        padding: 0 1;
    }
    """

    can_focus = True

    def __init__(self, data: _ChipData, *, selected: bool = False, id: str | None = None) -> None:
        super().__init__(id=id)
        self._data = data
        self._selected = selected
        self._theme = GLOBAL

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.refresh()

    def render(self) -> Visual:
        from rich.text import Text

        return Text.from_markup(self._render_str())

    def _render_str(self) -> str:
        d = self._data
        marker = "●" if self._selected else "○"
        if d.cpu_pct >= 90:
            bar_color = self._theme.needle_crit
        elif d.cpu_pct >= 70:
            bar_color = self._theme.needle_warn
        else:
            bar_color = self._theme.accent
        marker_color = self._theme.needle if self._selected else self._theme.tick
        return (
            f"[{marker_color}]{marker}[/] "
            f"[{self._theme.readout}]{d.label}[/] "
            f"CPU[{bar_color}]{_cpu_bar(d.cpu_pct)}[/] "
            f"[{self._theme.tick}]{d.cpu_pct:5.1f}%[/] "
            f"[{self._theme.tick}]RAM {d.mem_text}[/]"
        )


class AgentStrip(Horizontal):
    """Horizontal strip of agent chips. `selected_key` is reactive."""

    DEFAULT_CSS = """
    AgentStrip {
        height: 1;
        width: 1fr;
        border: solid $wire;
    }
    """

    selected_key: reactive[str] = reactive("", layout=False)

    class Selected(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._chips: list[_AgentChip] = []

    def set_agents(self, agents: Iterable[Agent], *, units: str = "binary") -> None:
        agents = tuple(agents)
        # remove old chips
        for child in list(self.children):
            child.remove()
        self._chips = []
        for agent in agents:
            data = _ChipData(
                key=agent.key,
                label=agent.descriptor_key,
                cpu_pct=agent.sample.cpu_pct,
                mem_text=_fmt_bytes(agent.sample.mem_used),
            )
            chip = _AgentChip(data, selected=agent.key == self.selected_key)
            self._chips.append(chip)
            self.mount(chip)

    def select(self, key: str) -> None:
        for chip in self._chips:
            chip.set_selected(chip._data.key == key)
        self.selected_key = key
        self.post_message(self.Selected(key))


__all__ = ["AgentStrip"]
