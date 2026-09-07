from __future__ import annotations

import time
from collections import deque
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from azrael.metrics.types import Agent, Sample, Timeseries
from azrael.platforms._common import ProcessMetrics

if TYPE_CHECKING:
    from azrael.agents.registry import Registry
    from azrael.platforms.backend import ResourceBackend


_SC_CLK_TCK: float = 100.0  # USER_HZ fallback; overridden by os.sysconf if needed


def _clk_tck() -> float:
    try:
        import os

        return float(os.sysconf("SC_CLK_TCK"))
    except (ValueError, OSError, AttributeError):
        return _SC_CLK_TCK


class Sampler:
    def __init__(
        self,
        backend: ResourceBackend,
        registry: Registry,
        *,
        ring_size: int = 720,
    ) -> None:
        self.backend: ResourceBackend = backend
        self.registry: Registry = registry
        self.ring_size: int = ring_size
        self._prev_cpu: dict[str, tuple[float, int]] = {}
        self._prev_proc: dict[int, tuple[float, int, int, int]] = {}
        self._ring: dict[str, deque[Sample]] = {}

    def tick(self) -> tuple[Agent, ...]:
        now = time.monotonic()
        agents: list[Agent] = []
        for scope in self.backend.discover_scopes():
            descriptor = self.registry.match_scope(Path(scope.path).name)
            if descriptor is None:
                continue
            m = self.backend.read_scope_metrics(scope)
            prev_t, prev_u = self._prev_cpu.get(scope.path, (now, m.cpu_usage_usec))
            dt = max(now - prev_t, 1e-6)
            quota_cores = m.cpu_quota_usec / m.cpu_period_usec if m.cpu_quota_usec > 0 else 1.0
            cpu_pct = (m.cpu_usage_usec - prev_u) / 1e6 / dt / max(quota_cores, 0.01) * 100
            self._prev_cpu[scope.path] = (now, m.cpu_usage_usec)
            throttle_pct = (m.throttled_usec / dt / 1e6 * 100) if dt > 0 else 0.0
            sample = Sample(
                timestamp=now,
                cpu_pct=cpu_pct,
                mem_used=m.mem_cur,
                mem_max=m.mem_max,
                throttle_pct=throttle_pct,
                oom_kills=m.oom_kill,
            )
            self._ring.setdefault(descriptor.key, deque(maxlen=self.ring_size)).append(sample)
            processes = self._compute_process_metrics(m.pids, now)
            agents.append(
                Agent(
                    key=descriptor.key,
                    descriptor_key=descriptor.key,
                    scope=scope,
                    processes=processes,
                    sample=sample,
                    caps=descriptor.default_caps,
                )
            )
        return tuple(agents)

    def history(self, agent_key: str) -> Timeseries:
        ring = self._ring.get(agent_key, ())
        return Timeseries(agent_key=agent_key, samples=tuple(ring))

    def _compute_process_metrics(
        self, pids: tuple[int, ...], now: float
    ) -> tuple[ProcessMetrics, ...]:
        tck = _clk_tck()
        out: list[ProcessMetrics] = []
        for pid in pids:
            try:
                pm = self.backend.read_process_metrics(pid)
            except (OSError, FileNotFoundError):
                self._prev_proc.pop(pid, None)
                continue
            prev = self._prev_proc.get(pid)
            if prev is None:
                self._prev_proc[pid] = (now, pm.cpu_ticks, pm.io_rchar, pm.io_wchar)
                out.append(pm)
                continue
            prev_t, prev_ticks, prev_rchar, prev_wchar = prev
            dt = max(now - prev_t, 1e-6)
            d_ticks = max(pm.cpu_ticks - prev_ticks, 0)
            cpu_pct = d_ticks / tck / dt * 100.0
            d_rchar = max(pm.io_rchar - prev_rchar, 0)
            d_wchar = max(pm.io_wchar - prev_wchar, 0)
            self._prev_proc[pid] = (now, pm.cpu_ticks, pm.io_rchar, pm.io_wchar)
            out.append(
                replace(
                    pm,
                    cpu_pct=cpu_pct,
                    io_rd_rate=d_rchar / dt,
                    io_wr_rate=d_wchar / dt,
                )
            )
        return tuple(out)


__all__ = ["Sampler"]
