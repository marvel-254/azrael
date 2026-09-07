from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from azrael.agents.descriptor import Caps
from azrael.platforms._common import ProcessMetrics, Scope


@dataclass(frozen=True)
class Sample:
    timestamp: float
    cpu_pct: float
    mem_used: int
    mem_max: int | None
    throttle_pct: float
    oom_kills: int


@dataclass(frozen=True)
class Timeseries:
    agent_key: str
    samples: tuple[Sample, ...]


@dataclass(frozen=True)
class Agent:
    key: str
    descriptor_key: str
    scope: Scope | None
    processes: tuple[ProcessMetrics, ...]
    sample: Sample
    caps: Caps
    sensor_mode: Literal["monitor-only", "control"] | None = None


__all__ = ["Agent", "Sample", "Timeseries"]
