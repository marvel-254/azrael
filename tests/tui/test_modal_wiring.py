"""Tests for wiring the TUI modal action handlers to `azrael.control`.

These instantiate `AzraelApp` against a fake backend, drive an action
handler synchronously, and assert the corresponding `control.actions`
function was called with the right arguments via `unittest.mock.patch`.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from azrael.agents.descriptor import AgentDescriptor, Caps
from azrael.agents.registry import Registry
from azrael.control.actions import ActionResult
from azrael.metrics.sampler import Sampler
from azrael.metrics.types import Agent, Sample
from azrael.platforms._common import ProcessMetrics, Scope, ScopeMetrics
from azrael.platforms.backend import ResourceBackend
from azrael.tui.app import AzraelApp


class _FakeBackend:
    name = "fake"
    capabilities = frozenset()

    def discover_scopes(self) -> list[Scope]:
        return []

    def read_scope_metrics(self, scope: Scope) -> ScopeMetrics:
        return ScopeMetrics(
            pids=(),
            cpu_usage_usec=0,
            cpu_quota_usec=0,
            cpu_period_usec=100_000,
            cpu_weight=100,
            nr_periods=0,
            nr_throttled=0,
            throttled_usec=0,
            mem_cur=0,
            mem_max=None,
            mem_high=None,
            mem_low=None,
            mem_pressure_avg10=0.0,
            oom_kill=0,
        )

    def read_process_metrics(self, pid: int) -> ProcessMetrics:
        return ProcessMetrics(
            pid=pid,
            ppid=1,
            cmd="",
            state="S",
            nice=0,
            cpu_ticks=0,
            cpu_pct=0.0,
            mem_rss=0,
            threads=1,
            io_rchar=0,
            io_wchar=0,
            io_rd_rate=0.0,
            io_wr_rate=0.0,
        )

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        pass

    def set_memory_max(self, scope: Scope, bytes: int) -> None:
        pass

    def set_memory_high(self, scope: Scope, bytes: int) -> None:
        pass

    def kill_scope(self, scope: Scope) -> None:
        pass

    def install_sensor(self, agent_descriptor: AgentDescriptor, cmd: list[str]) -> Scope:
        return Scope(self.name, "/tmp/sensor", None)

    def remove_sensor(self, scope: Scope) -> None:
        pass

    def discover_loose(self) -> dict[int, AgentDescriptor]:
        return {}

    def kill_pid(self, pid: int, sig: int = 15) -> None:
        pass

    def renice(self, pid: int, nice: int) -> None:
        pass


def _make_app() -> AzraelApp:
    backend: ResourceBackend = _FakeBackend()
    descriptor = AgentDescriptor(
        key="opencode",
        display_name="OpenCode",
        cmdline_needles=("opencode",),
        scope_fragments=("opencode",),
    )
    registry = Registry([descriptor])
    sampler = Sampler(backend, registry)
    return AzraelApp(sampler, backend)


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _make_agent(
    scope: Scope | None = None,
    caps: Caps | None = None,
) -> Agent:
    return Agent(
        key="opencode",
        descriptor_key="opencode",
        scope=scope,
        processes=(),
        sample=Sample(
            timestamp=0.0,
            cpu_pct=0.0,
            mem_used=0,
            mem_max=None,
            throttle_pct=0.0,
            oom_kills=0,
        ),
        caps=caps or Caps(),
    )


def test_action_kill_pid_calls_control_actions() -> None:
    """`k` (kill_pid) routes through `control.actions.kill_pid`."""
    app = _make_app()
    app._latest_agents = ()
    with (
        patch(
            "azrael.control.actions.kill_pid",
            return_value=ActionResult(ok=True, message="sent signal 15 to pid 4242"),
        ) as patched,
        patch.object(app, "_get_dashboard") as dash,
    ):
        dash.return_value.get_selected_pid.return_value = 4242
        _run(app.action_kill_pid())
    patched.assert_called_once()
    args = patched.call_args.args
    assert args[0] is app.backend
    assert args[1] == 4242


def test_action_kill_scope_calls_control_actions() -> None:
    """`K` (kill_scope) routes through `control.actions.kill_scope`."""
    app = _make_app()
    scope = Scope("fake", "/test.scope", None)
    app._latest_agents = (_make_agent(scope=scope),)
    app._focused_idx = 0

    with patch(
        "azrael.control.actions.kill_scope",
        return_value=ActionResult(ok=True, message=f"killed scope {scope.path}"),
    ) as patched:
        _run(app.action_kill_scope())
    patched.assert_called_once_with(app.backend, scope)


def test_action_weight_modal_pushes_weight_modal() -> None:
    """`W` pushes a `WeightModal` bound to the focused scope."""
    app = _make_app()
    scope = Scope("fake", "/test.scope", None)
    app._latest_agents = (_make_agent(scope=scope),)
    app._focused_idx = 0

    with (
        patch.object(app, "push_screen") as push,
        patch("azrael.tui.app.WeightModal") as modal_cls,
    ):
        _run(app.action_weight_modal())
    modal_cls.assert_called_once_with(app.backend, scope)
    push.assert_called_once()


def test_action_renice_modal_pushes_renice_modal() -> None:
    """`N` pushes a `ReniceModal` bound to the selected pid."""
    app = _make_app()
    with (
        patch.object(app, "push_screen") as push,
        patch("azrael.tui.app.ReniceModal") as modal_cls,
        patch.object(app, "_get_dashboard") as dash,
    ):
        dash.return_value.get_selected_pid.return_value = 1234
        _run(app.action_renice_modal())
    modal_cls.assert_called_once_with(app.backend, 1234)
    push.assert_called_once()


def test_action_caps_modal_pushes_caps_modal() -> None:
    """`C` pushes a `CapsModal` bound to the focused scope."""
    app = _make_app()
    scope = Scope("fake", "/test.scope", None)
    caps = Caps(cpu_weight=200, memory_max=1024, memory_high=512)
    app._latest_agents = (_make_agent(scope=scope, caps=caps),)
    app._focused_idx = 0

    with (
        patch.object(app, "push_screen") as push,
        patch("azrael.tui.app.CapsModal") as modal_cls,
    ):
        _run(app.action_caps_modal())
    modal_cls.assert_called_once_with(app.backend, scope, current_caps=caps)
    push.assert_called_once()
