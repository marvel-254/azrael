"""Apply a `Caps` to a `Scope` through a `ResourceBackend`.

Honors each capability flag the backend advertises; unsupported
operations are reported as `ActionResult(ok=False)` instead of
raising — the TUI can still render the partial-success.
"""

from __future__ import annotations

from azrael.agents.descriptor import Caps
from azrael.control import actions
from azrael.control.actions import ActionResult
from azrael.platforms._common import (
    CAP_CPU_WEIGHT,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    Scope,
)
from azrael.platforms.backend import ResourceBackend


def apply_caps(backend: ResourceBackend, scope: Scope, caps: Caps) -> tuple[ActionResult, ...]:
    """Apply each set field of ``caps`` to ``scope`` via ``backend``.

    Iterates ``caps.cpu_weight`` / ``memory_max`` / ``memory_high``
    (the fields the cgroup backend understands). For each:

    - If the backend lacks the matching capability, an
      `ActionResult(ok=False, error=...)` is appended without
      calling the backend.
    - Otherwise the appropriate ``control.actions.set_*`` is called
      and its `ActionResult` appended.

    Nice is intentionally not applied here — nice is a per-process
    property, not a scope property.
    """
    results: list[ActionResult] = []
    if caps.cpu_weight is not None:
        if CAP_CPU_WEIGHT not in backend.capabilities:
            results.append(
                ActionResult(
                    ok=False,
                    message="",
                    error=f"backend does not support {CAP_CPU_WEIGHT}",
                )
            )
        else:
            results.append(actions.set_cpu_weight(backend, scope, caps.cpu_weight))
    if caps.memory_max is not None:
        if CAP_MEMORY_MAX not in backend.capabilities:
            results.append(
                ActionResult(
                    ok=False,
                    message="",
                    error=f"backend does not support {CAP_MEMORY_MAX}",
                )
            )
        else:
            results.append(actions.set_memory_max(backend, scope, caps.memory_max))
    if caps.memory_high is not None:
        if CAP_MEMORY_HIGH not in backend.capabilities:
            results.append(
                ActionResult(
                    ok=False,
                    message="",
                    error=f"backend does not support {CAP_MEMORY_HIGH}",
                )
            )
        else:
            results.append(actions.set_memory_high(backend, scope, caps.memory_high))
    return tuple(results)


__all__ = ["apply_caps"]
