"""Dashboard screen — the main view.

Composes (per PLAN §9):
- AgentStrip (top)
- 3 gauges row (system, focused agent, memory)
- Sparkline of focused agent CPU history
- ProcessTable (middle, fills the rest)
- KeybindFooter (bottom)

The App owns the timer and pushes the latest `World` to this screen via
`update(agents, focused_key)`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Static

from azrael.metrics.types import Agent
from azrael.tui.theme import GLOBAL, Theme
from azrael.tui.widgets.agent_strip import AgentStrip
from azrael.tui.widgets.gauge import AnalogGauge
from azrael.tui.widgets.keybind_footer import KeybindFooter
from azrael.tui.widgets.process_table import ProcessTable, SortKey
from azrael.tui.widgets.sparkline import Sparkline


@dataclass(frozen=True)
class _Snapshot:
    agents: tuple[Agent, ...]
    focused_key: str
    system_cpu_pct: float
    system_mem_used: int
    system_mem_total: int


class DashboardScreen(Screen[None]):
    DEFAULT_CSS = """
    DashboardScreen {
        layout: vertical;
        background: $bg;
    }
    #strip {
        height: 1;
    }
    #gauge_row {
        height: 5;
    }
    #spark_row {
        height: 1;
        border: solid $wire;
    }
    #proc {
        height: 1fr;
    }
    #footer {
        height: 1;
    }
    #focused_label {
        height: 1;
        padding: 0 1;
        color: $tick;
    }
    """

    _SORT_KEYS: ClassVar[dict[str, SortKey]] = {
        "c": "cpu",
        "m": "mem",
        "p": "pid",
        "n": "name",
        "i": "io",
    }

    def __init__(self, *, theme: Theme = GLOBAL) -> None:
        super().__init__()
        self._theme = theme
        self._focused_idx = 0
        self._latest: _Snapshot | None = None

    def compose(self):  # type: ignore[no-untyped-def]
        yield AgentStrip(id="strip")
        yield FocusedLabel(id="focused_label")
        with Horizontal(id="gauge_row"):
            yield AnalogGauge("System", id="g_system", theme=self._theme)
            yield AnalogGauge("Agent", id="g_agent", theme=self._theme)
            yield AnalogGauge("Memory", id="g_memory", theme=self._theme)
        yield Sparkline(id="spark_row")
        yield ProcessTable(id="proc")
        yield KeybindFooter(id="footer")

    def update(
        self,
        agents: tuple[Agent, ...],
        system_cpu_pct: float,
        system_mem_used: int,
        system_mem_total: int,
        history: Sequence[float] = (),
    ) -> None:
        if not agents:
            self._latest = None
            return
        idx = max(0, min(self._focused_idx, len(agents) - 1))
        self._focused_idx = idx
        focused = agents[idx]
        snap = _Snapshot(
            agents=agents,
            focused_key=focused.key,
            system_cpu_pct=system_cpu_pct,
            system_mem_used=system_mem_used,
            system_mem_total=system_mem_total,
        )
        self._latest = snap

        strip = self.query_one("#strip", AgentStrip)
        strip.set_agents(agents)
        strip.select(focused.key)

        g_system = self.query_one("#g_system", AnalogGauge)
        g_agent = self.query_one("#g_agent", AnalogGauge)
        g_memory = self.query_one("#g_memory", AnalogGauge)
        g_system.set_value(system_cpu_pct)
        g_agent.set_value(focused.sample.cpu_pct)
        mem_pct = (system_mem_used / system_mem_total * 100.0) if system_mem_total > 0 else 0.0
        g_memory.set_value(mem_pct)

        spark = self.query_one("#spark_row", Sparkline)
        spark.set_samples(history)

        table = self.query_one("#proc", ProcessTable)
        table.set_processes(focused.processes)

        label = self.query_one("#focused_label", FocusedLabel)
        label.update(f"Focused: {focused.descriptor_key} · scope: {_scope_path(focused)}")

    def cycle_focus(self, delta: int) -> None:
        if self._latest is None or not self._latest.agents:
            return
        n = len(self._latest.agents)
        self._focused_idx = (self._focused_idx + delta) % n
        self._refresh_from_cache()

    def set_sort(self, key: SortKey) -> None:
        table = self.query_one("#proc", ProcessTable)
        table.set_sort(key)

    def get_selected_pid(self) -> int:
        return self.query_one("#proc", ProcessTable).get_selected_pid()

    def set_footer_context(self, ctx: str) -> None:
        self.query_one("#footer", KeybindFooter).set_context(ctx)

    def _refresh_from_cache(self) -> None:
        if self._latest is None:
            return
        snap = self._latest
        self.update(snap.agents, snap.system_cpu_pct, snap.system_mem_used, snap.system_mem_total)


class FocusedLabel(Static):
    DEFAULT_CSS = """
    FocusedLabel {
        height: 1;
        padding: 0 1;
        background: $bezel;
    }
    """


def _scope_path(agent: Agent) -> str:
    if agent.scope is None:
        return "(loose)"
    return agent.scope.path


__all__ = ["DashboardScreen"]
