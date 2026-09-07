from __future__ import annotations

from dataclasses import dataclass

CAP_CPU_WEIGHT: str = "cpu.weight"
CAP_MEMORY_MAX: str = "memory.max"
CAP_MEMORY_HIGH: str = "memory.high"
CAP_SENSOR: str = "sensor"
CAP_KILL_SCOPE: str = "kill_scope"
CAP_CPU_QUOTA: str = "cpu.quota"

Capabilities = frozenset[str]


@dataclass(frozen=True)
class Scope:
    backend_name: str
    path: str
    leader_pid: int | None


@dataclass(frozen=True)
class ScopeMetrics:
    pids: tuple[int, ...]
    cpu_usage_usec: int
    cpu_quota_usec: int
    cpu_period_usec: int
    cpu_weight: int
    nr_periods: int
    nr_throttled: int
    throttled_usec: int
    mem_cur: int
    mem_max: int | None
    mem_high: int | None
    mem_low: int | None
    mem_pressure_avg10: float
    oom_kill: int


@dataclass(frozen=True)
class ProcessMetrics:
    pid: int
    ppid: int
    cmd: str
    state: str
    nice: int
    cpu_ticks: int
    cpu_pct: float
    mem_rss: int
    threads: int
    io_rchar: int
    io_wchar: int
    io_rd_rate: float
    io_wr_rate: float


__all__ = [
    "CAP_CPU_QUOTA",
    "CAP_CPU_WEIGHT",
    "CAP_KILL_SCOPE",
    "CAP_MEMORY_HIGH",
    "CAP_MEMORY_MAX",
    "CAP_SENSOR",
    "Capabilities",
    "ProcessMetrics",
    "Scope",
    "ScopeMetrics",
]
