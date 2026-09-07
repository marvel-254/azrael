"""azrael TUI app — the Textual `App` subclass.

Wires a `Sampler` to a 1-second timer that refreshes the dashboard.
Keybinds per PLAN Appendix B. The N/W/C modals push real control
screens that call `azrael.control`.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from azrael.control import actions as control_actions
from azrael.metrics.sampler import Sampler
from azrael.metrics.types import Agent
from azrael.platforms.backend import ResourceBackend
from azrael.tui.screens.dashboard import DashboardScreen
from azrael.tui.screens.first_run import FirstRunScreen
from azrael.tui.screens.modal_caps import CapsModal
from azrael.tui.screens.modal_renice import ReniceModal
from azrael.tui.screens.modal_weight import WeightModal
from azrael.tui.theme import GLOBAL
from azrael.tui.widgets.process_table import SortKey


class _PlaceholderModal(ModalScreen[None]):
    """A minimal modal used during Phase 5 for unimplemented actions."""

    DEFAULT_CSS = """
    _PlaceholderModal {
        align: center middle;
    }
    _PlaceholderModal > Static {
        width: 50;
        height: 5;
        border: solid $wire;
        padding: 1;
    }
    """

    def __init__(self, action: str) -> None:
        super().__init__()
        self._action = action

    def compose(self):  # type: ignore[no-untyped-def]
        yield Static(f"Coming soon: {self._action}\n\nPress Esc to dismiss.")

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key == "escape":
            self.dismiss(None)


_BindingsList = list[Binding | tuple[str, str] | tuple[str, str, str]]


class AzraelApp(App[None]):
    """The azrael TUI."""

    CSS = """
    Screen {
        background: $bg;
    }
    """

    BINDINGS: ClassVar[_BindingsList] = [
        Binding("q", "quit", "Quit"),
        Binding("Q", "quit", "Quit", show=False),
        Binding("escape", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("left", "prev_agent", "←"),
        Binding("right", "next_agent", "→"),
        Binding("up", "row_up", "↑"),
        Binding("down", "row_down", "↓"),
        Binding("c", "sort_cpu", "c"),
        Binding("m", "sort_mem", "m"),
        Binding("p", "sort_pid", "p"),
        Binding("n", "sort_name", "n"),
        Binding("i", "sort_io", "i"),
        Binding("k", "kill_pid", "k"),
        Binding("K", "kill_scope", "K"),
        Binding("N", "renice_modal", "N"),
        Binding("W", "weight_modal", "W"),
        Binding("C", "caps_modal", "C"),
        Binding("u", "toggle_units", "u"),
        Binding("question_mark", "help", "?"),
        Binding("ctrl+l", "redraw", "Ctrl-L"),
    ]

    def __init__(
        self,
        sampler: Sampler,
        backend: ResourceBackend,
        *,
        interval_s: float = 1.0,
    ) -> None:
        super().__init__()
        self.sampler: Sampler = sampler
        self.backend: ResourceBackend = backend
        self._interval_s = interval_s
        self._focused_idx = 0
        self._sort_key: SortKey = "cpu"
        self._units = "binary"
        self._latest_agents: tuple[Agent, ...] = ()
        self._system_cpu_pct = 0.0
        self._system_mem_used = 0
        self._system_mem_total = 1
        self._pushed_dashboard = False

    def on_mount(self) -> None:
        self.push_screen(FirstRunScreen())
        self.set_interval(self._interval_s, self._tick)

    def _tick(self) -> None:
        try:
            agents = self.sampler.tick()
        except Exception:
            return
        self._latest_agents = agents
        if agents:
            self._system_cpu_pct = sum(a.sample.cpu_pct for a in agents) / len(agents)
            self._system_mem_used = sum(a.sample.mem_used for a in agents)
        if not self._pushed_dashboard and agents:
            self._pushed_dashboard = True
            self.push_screen(DashboardScreen(theme=GLOBAL))
        dash = self._get_dashboard()
        if dash is not None:
            history = tuple(s.cpu_pct for s in self.sampler.history(self._focused_key()).samples)
            dash.update(
                self._latest_agents,
                self._system_cpu_pct,
                self._system_mem_used,
                self._system_mem_total,
                history=history,
            )

    def _get_dashboard(self) -> DashboardScreen | None:
        for screen in self.screen_stack:
            if isinstance(screen, DashboardScreen):
                return screen
        return None

    def _focused_key(self) -> str:
        if not self._latest_agents:
            return ""
        idx = max(0, min(self._focused_idx, len(self._latest_agents) - 1))
        return self._latest_agents[idx].key

    async def action_refresh(self) -> None:
        self._tick()

    async def action_prev_agent(self) -> None:
        if not self._latest_agents:
            return
        self._focused_idx = (self._focused_idx - 1) % len(self._latest_agents)
        dash = self._get_dashboard()
        if dash is not None:
            dash.cycle_focus(-1)

    async def action_next_agent(self) -> None:
        if not self._latest_agents:
            return
        self._focused_idx = (self._focused_idx + 1) % len(self._latest_agents)
        dash = self._get_dashboard()
        if dash is not None:
            dash.cycle_focus(1)

    async def action_row_up(self) -> None:
        self._table_action("cursor_up")

    async def action_row_down(self) -> None:
        self._table_action("cursor_down")

    def _table_action(self, action: str) -> None:
        dash = self._get_dashboard()
        if dash is None:
            return
        try:
            table = dash.query_one("#proc")
            getattr(table, action)()
        except Exception:
            return

    async def action_sort_cpu(self) -> None:
        self._sort_key = "cpu"
        self._apply_sort()

    async def action_sort_mem(self) -> None:
        self._sort_key = "mem"
        self._apply_sort()

    async def action_sort_pid(self) -> None:
        self._sort_key = "pid"
        self._apply_sort()

    async def action_sort_name(self) -> None:
        self._sort_key = "name"
        self._apply_sort()

    async def action_sort_io(self) -> None:
        self._sort_key = "io"
        self._apply_sort()

    def _apply_sort(self) -> None:
        dash = self._get_dashboard()
        if dash is not None:
            dash.set_sort(self._sort_key)

    async def action_kill_pid(self) -> None:
        dash = self._get_dashboard()
        if dash is None:
            return
        pid = dash.get_selected_pid()
        if pid <= 0:
            return
        control_actions.kill_pid(self.backend, pid)

    async def action_kill_scope(self) -> None:
        if not self._latest_agents:
            return
        agent = self._latest_agents[self._focused_idx]
        scope = agent.scope
        if scope is None:
            return
        control_actions.kill_scope(self.backend, scope)

    async def action_renice_modal(self) -> None:
        dash = self._get_dashboard()
        if dash is None:
            return
        pid = dash.get_selected_pid()
        if pid <= 0:
            return
        self.push_screen(ReniceModal(self.backend, pid))

    async def action_weight_modal(self) -> None:
        if not self._latest_agents:
            return
        agent = self._latest_agents[self._focused_idx]
        scope = agent.scope
        if scope is None:
            return
        self.push_screen(WeightModal(self.backend, scope))

    async def action_caps_modal(self) -> None:
        if not self._latest_agents:
            return
        agent = self._latest_agents[self._focused_idx]
        scope = agent.scope
        if scope is None:
            return
        self.push_screen(CapsModal(self.backend, scope, current_caps=agent.caps))

    async def action_toggle_units(self) -> None:
        self._units = "si" if self._units == "binary" else "binary"

    async def action_help(self) -> None:
        self.push_screen(_PlaceholderModal("help"))

    async def action_redraw(self) -> None:
        self.refresh()


__all__ = ["AzraelApp"]
