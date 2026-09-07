from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from azrael.metrics.types import Agent

if TYPE_CHECKING:
    from azrael.agents.descriptor import AgentDescriptor
    from azrael.platforms.backend import ResourceBackend


def unify(
    scope_agents: Iterable[Agent],
    loose_pids: Mapping[int, AgentDescriptor],
    backend: ResourceBackend | None,
) -> tuple[Agent, ...]:
    """Merge scope-derived agents with loose-process agents.

    Phase 4: scope agents pass through unchanged. Loose-process wiring is a
    TODO; future iterations will construct synthetic `Agent` rows from
    `loose_pids` using a synthetic `Scope` of `path=/proc/<pid>` and a
    delta-derived cpu_pct.
    """
    _ = loose_pids, backend  # silence unused-arg lint; kept for API parity
    return tuple(scope_agents)


__all__ = ["unify"]
