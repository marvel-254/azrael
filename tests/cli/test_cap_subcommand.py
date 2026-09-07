"""Tests for the `azrael cap` CLI subcommand.

Drives `cap` via `click.testing.CliRunner`, monkeypatching the backend
and sampler so we don't touch real cgroups.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from click.testing import CliRunner

from azrael.agents.descriptor import AgentDescriptor
from azrael.agents.registry import Registry
from azrael.cli.main import main
from azrael.metrics.sampler import Sampler
from azrael.metrics.types import Agent, Sample
from azrael.platforms._common import (
    CAP_CPU_WEIGHT,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    Capabilities,
    ProcessMetrics,
    Scope,
    ScopeMetrics,
)


@dataclass
class _RecordingBackend:
    name: str = "fake"
    capabilities: Capabilities = field(
        default_factory=lambda: frozenset({CAP_CPU_WEIGHT, CAP_MEMORY_MAX, CAP_MEMORY_HIGH})
    )
    set_cpu_weight_calls: list[tuple[Scope, int]] = field(default_factory=list)
    set_memory_max_calls: list[tuple[Scope, int]] = field(default_factory=list)
    set_memory_high_calls: list[tuple[Scope, int]] = field(default_factory=list)
    raise_on: str | None = None

    def _maybe_raise(self, op: str) -> None:
        if self.raise_on == op:
            raise RuntimeError(f"boom in {op}")

    def discover_scopes(self) -> list[Scope]:
        return [self._scope()]

    def read_scope_metrics(self, scope: Scope) -> ScopeMetrics:
        return ScopeMetrics(
            pids=(4242,),
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
            cmd="opencode",
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

    def _scope(self) -> Scope:
        return Scope(self.name, "/test.scope", 4242)

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        self.set_cpu_weight_calls.append((scope, weight))
        self._maybe_raise("set_cpu_weight")

    def set_memory_max(self, scope: Scope, bytes: int) -> None:
        self.set_memory_max_calls.append((scope, bytes))
        self._maybe_raise("set_memory_max")

    def set_memory_high(self, scope: Scope, bytes: int) -> None:
        self.set_memory_high_calls.append((scope, bytes))
        self._maybe_raise("set_memory_high")

    def kill_scope(self, scope: Scope) -> None:
        pass

    def install_sensor(self, agent_descriptor: AgentDescriptor, cmd: list[str]) -> Scope:
        return self._scope()

    def remove_sensor(self, scope: Scope) -> None:
        pass

    def discover_loose(self) -> dict[int, AgentDescriptor]:
        return {}

    def kill_pid(self, pid: int, sig: int = 15) -> None:
        pass

    def renice(self, pid: int, nice: int) -> None:
        pass


def _patched_agent(target_scope: Scope) -> Agent:
    return Agent(
        key="opencode",
        descriptor_key="opencode",
        scope=target_scope,
        processes=(),
        sample=Sample(
            timestamp=0.0,
            cpu_pct=0.0,
            mem_used=0,
            mem_max=None,
            throttle_pct=0.0,
            oom_kills=0,
        ),
        caps=None,  # type: ignore[arg-type]
    )


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch) -> _RecordingBackend:
    b = _RecordingBackend()
    scope = b._scope()

    def fake_detect() -> _RecordingBackend:
        return b

    def fake_sampler_factory(_backend: _RecordingBackend, _registry: Registry) -> Sampler:
        class _StubSampler:
            def tick(self) -> tuple[Agent, ...]:
                return (_patched_agent(scope),)

            def history(self, _key: str):
                from azrael.metrics.types import Timeseries

                return Timeseries(agent_key="opencode", samples=())

        return _StubSampler()  # type: ignore[return-value]

    monkeypatch.setattr("azrael.cli.main.detect", fake_detect)
    monkeypatch.setattr("azrael.cli.main.Sampler", fake_sampler_factory)
    return b


def test_cap_cpu_weight_calls_backend(backend: _RecordingBackend) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["cap", "--agent", "opencode", "--cpu-weight", "200"],
    )
    assert result.exit_code == 0, result.output
    assert "200" in result.output
    assert backend.set_cpu_weight_calls == [(backend._scope(), 200)]


def test_cap_memory_options_use_control_parser(backend: _RecordingBackend) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "cap",
            "--agent",
            "opencode",
            "--memory-max",
            "4G",
            "--memory-high",
            "2G",
        ],
    )
    assert result.exit_code == 0, result.output
    assert backend.set_memory_max_calls == [(backend._scope(), 4 * 1024**3)]
    assert backend.set_memory_high_calls == [(backend._scope(), 2 * 1024**3)]


def test_cap_with_no_options_errors(backend: _RecordingBackend) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["cap", "--agent", "opencode"])
    assert result.exit_code != 0


def test_cap_propagates_backend_errors(backend: _RecordingBackend) -> None:
    backend.raise_on = "set_cpu_weight"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["cap", "--agent", "opencode", "--cpu-weight", "200"],
    )
    assert result.exit_code != 0
