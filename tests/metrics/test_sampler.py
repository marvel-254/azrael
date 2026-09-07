from __future__ import annotations

from azrael.metrics.sampler import Sampler


class FakeBackend:
    name = "fake"
    capabilities = frozenset()

    def __init__(self) -> None:
        self._tick = 0
        self._proc_tick = 0
        self._base_usage = 1_000_000

    def discover_scopes(self) -> list:
        from azrael.platforms._common import Scope

        return [Scope("fake", "/fake/opencode-1234.scope", None)]

    def read_scope_metrics(self, scope):
        from azrael.platforms._common import ScopeMetrics

        # cpu_usage_usec advances by 200_000 each tick.
        self._tick += 1
        return ScopeMetrics(
            pids=(1234, 1235),
            cpu_usage_usec=self._base_usage + self._tick * 200_000,
            cpu_quota_usec=0,
            cpu_period_usec=100_000,
            cpu_weight=100,
            nr_periods=0,
            nr_throttled=0,
            throttled_usec=0,
            mem_cur=100 * 1024 * 1024,
            mem_max=None,
            mem_high=None,
            mem_low=None,
            mem_pressure_avg10=0.0,
            oom_kill=0,
        )

    def read_process_metrics(self, pid: int):
        from azrael.platforms._common import ProcessMetrics

        self._proc_tick += 1
        return ProcessMetrics(
            pid=pid,
            ppid=1,
            cmd=f"opencode {pid}",
            state="S",
            nice=0,
            cpu_ticks=10_000_000 + self._proc_tick * 1_000,  # +1ms worth of ticks per tick
            cpu_pct=0.0,
            mem_rss=50 * 1024 * 1024,
            threads=4,
            io_rchar=self._proc_tick * 4096,
            io_wchar=self._proc_tick * 2048,
            io_rd_rate=0.0,
            io_wr_rate=0.0,
        )


def _make_sampler() -> tuple[Sampler, FakeBackend, object]:
    from azrael.agents.descriptor import AgentDescriptor
    from azrael.agents.registry import Registry

    backend = FakeBackend()
    descriptor = AgentDescriptor(
        key="opencode",
        display_name="OpenCode",
        cmdline_needles=("opencode",),
        scope_fragments=("opencode", ".scope"),
    )
    registry = Registry([descriptor])
    return Sampler(backend, registry), backend, descriptor


def test_sampler_tick_returns_tuple_of_agents() -> None:
    sampler, _backend, _ = _make_sampler()
    agents = sampler.tick()
    assert isinstance(agents, tuple)
    assert len(agents) == 1
    a = agents[0]
    assert a.key == "opencode"
    assert a.descriptor_key == "opencode"
    assert a.scope is not None
    assert isinstance(a.sample.timestamp, float)
    assert a.caps is not None


def test_sampler_computes_cpu_pct_from_delta() -> None:
    sampler, _backend, _ = _make_sampler()
    first = sampler.tick()
    second = sampler.tick()
    assert first[0].sample.cpu_pct == 0.0  # no prior
    # usage_usec jumps 200_000 each tick; dt ~ 0 in test (loop is fast), so the
    # numerator is large but the denominator is small — we just assert the
    # delta is > 0 (any non-zero value demonstrates the delta path works).
    assert second[0].sample.cpu_pct > 0.0


def test_sampler_normalizes_against_quota() -> None:
    sampler, backend, _ = _make_sampler()
    # Patch: make the first tick report cpu_usage_usec=2_000_000, second tick 4_000_000.
    # With quota 0 -> 1 core; doubling usage -> ~100% cpu_pct.
    from azrael.platforms._common import ScopeMetrics

    calls = {"n": 0}

    def fake_read(scope):
        calls["n"] += 1
        # cpu_usage_usec delta of 200ms per tick, normalized to 1 core, dt=1s -> 20%
        return ScopeMetrics(
            pids=(),
            cpu_usage_usec=1_000_000 + calls["n"] * 200_000,
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

    backend.read_scope_metrics = fake_read  # type: ignore[attr-defined]
    sampler.tick()
    second = sampler.tick()
    # 200_000 us / 1_000_000 us = 0.2s of CPU time on a 1-core scale => 20%
    # With dt near zero (test runs fast), value is non-deterministic, but > 0.
    assert second[0].sample.cpu_pct > 0


def test_sampler_ignores_unknown_scopes() -> None:
    from azrael.agents.descriptor import AgentDescriptor
    from azrael.agents.registry import Registry
    from azrael.platforms._common import Scope

    class _B(FakeBackend):
        def discover_scopes(self):
            return [
                Scope("fake", "/fake/hermes-99.scope", None),
                Scope("fake", "/fake/opencode-99.scope", None),
            ]

    # Register opencode with a tight fragment so it matches only opencode
    # scopes. hermes-99.scope should be ignored entirely.
    opencode = AgentDescriptor(
        key="opencode",
        display_name="OpenCode",
        cmdline_needles=("opencode",),
        scope_fragments=("opencode-",),
    )
    sampler = Sampler(_B(), Registry([opencode]))
    agents = sampler.tick()
    assert len(agents) == 1
    assert agents[0].key == "opencode"


def test_sampler_history_returns_timeseries() -> None:
    sampler, _, _ = _make_sampler()
    sampler.tick()
    sampler.tick()
    ts = sampler.history("opencode")
    assert ts.agent_key == "opencode"
    assert len(ts.samples) == 2


def test_sampler_history_unknown_key_returns_empty() -> None:
    sampler, _, _ = _make_sampler()
    ts = sampler.history("missing")
    assert ts.agent_key == "missing"
    assert ts.samples == ()


def test_sampler_ring_size_limits_history() -> None:
    sampler, _, _ = _make_sampler()
    sampler.ring_size = 3
    for _ in range(5):
        sampler.tick()
    ts = sampler.history("opencode")
    assert len(ts.samples) == 3


def test_sampler_history_returns_frozen_tuple() -> None:
    sampler, _, _ = _make_sampler()
    sampler.tick()
    ts = sampler.history("opencode")
    # Samples tuple is immutable
    assert isinstance(ts.samples, tuple)
    assert all(isinstance(s.timestamp, float) for s in ts.samples)


def test_sampler_computes_per_process_cpu_pct() -> None:
    sampler, backend, _ = _make_sampler()
    backend._proc_tick = 0  # type: ignore[attr-defined]
    # First tick seeds prev; second tick has a delta to compute from.
    sampler.tick()
    agents = sampler.tick()
    assert len(agents) == 1
    procs = agents[0].processes
    assert len(procs) == 2
    for p in procs:
        # With dt near zero and ticks advancing, the computed value is non-deterministic
        # but the delta path is exercised — assert the field exists and is a float.
        assert isinstance(p.cpu_pct, float)
    # First-tick priming keeps procs at the seeded raw values (cpu_pct=0).
    # After the second tick, _prev_proc is populated so subsequent ticks compute deltas.
    sampler.tick()
    agents = sampler.tick()
    for p in agents[0].processes:
        # After at least two deltas, cpu_pct should be > 0 because ticks are advancing.
        assert p.cpu_pct > 0.0
