from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Caps:
    cpu_weight: int | None = None
    memory_max: int | None = None
    memory_high: int | None = None
    nice: int | None = None
    oom_policy: Literal["kill", "stop", "continue"] | None = None


_OOM = Literal["kill", "stop", "continue"]


@dataclass(frozen=True)
class AgentDescriptor:
    key: str
    display_name: str
    cmdline_needles: tuple[str, ...]
    scope_fragments: tuple[str, ...]
    user_log_paths: tuple[Path, ...] = ()
    config_path_hints: tuple[Path, ...] = ()
    default_caps: Caps = field(default_factory=Caps)
    sensor_template: str | None = None
    website: str | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("descriptor key must be non-empty")
        if not self.key.islower() or not all(c.isalnum() or c == "-" for c in self.key):
            raise ValueError(f"descriptor key {self.key!r} must be lowercase alnum+dash only")
        # Coerce Path-like tuples
        object.__setattr__(self, "user_log_paths", tuple(Path(p) for p in self.user_log_paths))
        object.__setattr__(
            self,
            "config_path_hints",
            tuple(Path(p) for p in self.config_path_hints),
        )


__all__ = ["AgentDescriptor", "Caps"]
