from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from azrael.platforms._common import (
    Capabilities,
    ProcessMetrics,
    Scope,
    ScopeMetrics,
)

if TYPE_CHECKING:
    from azrael.agents.descriptor import AgentDescriptor


class ResourceBackend(Protocol):
    name: str
    capabilities: Capabilities

    def discover_scopes(self) -> list[Scope]: ...
    def read_scope_metrics(self, scope: Scope) -> ScopeMetrics: ...
    def set_cpu_weight(self, scope: Scope, weight: int) -> None: ...
    def set_memory_max(self, scope: Scope, bytes: int) -> None: ...
    def set_memory_high(self, scope: Scope, bytes: int) -> None: ...
    def kill_scope(self, scope: Scope) -> None: ...
    def install_sensor(self, agent_descriptor: AgentDescriptor, cmd: list[str]) -> Scope: ...
    def remove_sensor(self, scope: Scope) -> None: ...

    def discover_loose(self) -> dict[int, AgentDescriptor]: ...
    def read_process_metrics(self, pid: int) -> ProcessMetrics: ...
    def kill_pid(self, pid: int, sig: int = 15) -> None: ...
    def renice(self, pid: int, nice: int) -> None: ...


def detect(cgroup_root: str = "/sys/fs/cgroup") -> ResourceBackend:
    from azrael.platforms.linux_cgroup_v2 import LinuxCgroupV2Backend

    if Path(cgroup_root).is_dir():
        return LinuxCgroupV2Backend(cgroup_root=cgroup_root)
    raise RuntimeError(
        f"no ResourceBackend available: {cgroup_root} is not a cgroup v2 mount. "
        "Windows + macOS backends are added in Phase 9."
    )


__all__ = ["ResourceBackend", "detect"]
