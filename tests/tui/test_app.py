"""Tests for the AzraelApp construction."""

from __future__ import annotations

from azrael.agents.descriptor import AgentDescriptor
from azrael.agents.registry import Registry
from azrael.metrics.sampler import Sampler
from azrael.platforms._common import (
    ProcessMetrics,
    Scope,
    ScopeMetrics,
)
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


def test_app_constructs_with_sampler_and_backend() -> None:
    app = _make_app()
    assert app.sampler is not None
    assert app.backend is not None


def test_app_has_expected_bindings() -> None:
    app = _make_app()
    assert len(app.BINDINGS) >= 15
    keys = {b.key for b in app.BINDINGS}
    assert "q" in keys
    assert "r" in keys
    assert "left" in keys
    assert "right" in keys
    assert "k" in keys
    assert "?" in keys or "question_mark" in keys


def test_app_focused_idx_initial_zero() -> None:
    app = _make_app()
    assert app._focused_idx == 0
