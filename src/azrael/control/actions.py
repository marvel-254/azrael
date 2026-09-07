"""Thin wrappers over `ResourceBackend` control operations.

Each function returns an `ActionResult` — exceptions are caught and
converted so the TUI / CLI can render them as warnings instead of
crashing the loop. Validation happens *before* the backend is called:
a bad value raises `ValueError` and the caller decides how to render.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from azrael.platforms._common import Scope
from azrael.platforms.backend import ResourceBackend


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str
    error: str | None = None


def _from_oserror(exc: OSError) -> str:
    """Render an OSError into a human-readable string for the TUI."""
    if isinstance(exc, FileNotFoundError):
        return f"not found: {exc.filename or exc.strerror or str(exc)}"
    if isinstance(exc, PermissionError):
        return f"permission denied: {exc.strerror or exc.filename or str(exc)}"
    if isinstance(exc, ProcessLookupError):
        return f"process gone: {exc.strerror or str(exc)}"
    if exc.errno:
        return os.strerror(exc.errno) or str(exc)
    return exc.strerror or str(exc)


def kill_pid(backend: ResourceBackend, pid: int, sig: int = 15) -> ActionResult:
    """Send `sig` to `pid` via the backend.

    Raises `ValueError` for invalid pid / signal *before* touching the
    backend. Returns an `ActionResult` describing the outcome.
    """
    if pid <= 0:
        raise ValueError(f"pid must be > 0, got {pid}")
    if not 0 <= sig <= 64:
        raise ValueError(f"signal must be 0..64, got {sig}")
    try:
        backend.kill_pid(pid, sig)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError) as exc:
        return ActionResult(ok=False, message="", error=_from_oserror(exc))
    return ActionResult(ok=True, message=f"sent signal {sig} to pid {pid}")


def kill_scope(backend: ResourceBackend, scope: Scope) -> ActionResult:
    """Stop a systemd --user scope via the backend (which calls systemctl)."""
    if not scope.path:
        raise ValueError("scope.path must be non-empty")
    try:
        backend.kill_scope(scope)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        return ActionResult(
            ok=False,
            message="",
            error=f"systemctl failed (rc={exc.returncode}): {stderr or exc!r}",
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return ActionResult(ok=False, message="", error=_from_oserror(exc))
    return ActionResult(ok=True, message=f"killed scope {scope.path}")


def set_cpu_weight(backend: ResourceBackend, scope: Scope, weight: int) -> ActionResult:
    """Write `cpu.weight` (1..10000) on the scope's cgroup."""
    if not 1 <= weight <= 10000:
        raise ValueError(f"cpu.weight must be 1..10000, got {weight}")
    try:
        backend.set_cpu_weight(scope, weight)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError) as exc:
        return ActionResult(ok=False, message="", error=_from_oserror(exc))
    return ActionResult(ok=True, message=f"cpu.weight set to {weight}")


def set_memory_max(backend: ResourceBackend, scope: Scope, bytes_: int | None) -> ActionResult:
    """Write `memory.max`. ``None`` (or the unlimited sentinel ``-1``)
    writes the cgroup v2 sentinel ``"max\\n"``.
    """
    if bytes_ is not None and bytes_ < 0:
        raise ValueError(f"memory.max must be >= 0, got {bytes_}")
    if bytes_ is None:
        # Unlimited: the backend writes "max\n" itself; we keep the
        # public contract simple — None means "unlimited".
        backend.set_memory_max(scope, -1)
    else:
        backend.set_memory_max(scope, bytes_)
    return ActionResult(
        ok=True,
        message="memory.max unset (unlimited)"
        if bytes_ is None
        else f"memory.max set to {bytes_} B",
    )


def set_memory_high(backend: ResourceBackend, scope: Scope, bytes_: int | None) -> ActionResult:
    """Write `memory.high`. ``None`` / ``-1`` means "unlimited"."""
    if bytes_ is not None and bytes_ < 0:
        raise ValueError(f"memory.high must be >= 0, got {bytes_}")
    if bytes_ is None:
        backend.set_memory_high(scope, -1)
    else:
        backend.set_memory_high(scope, bytes_)
    return ActionResult(
        ok=True,
        message="memory.high unset (unlimited)"
        if bytes_ is None
        else f"memory.high set to {bytes_} B",
    )


def renice(backend: ResourceBackend, pid: int, nice: int) -> ActionResult:
    """Change a process's nice value (-20..19)."""
    if pid <= 0:
        raise ValueError(f"pid must be > 0, got {pid}")
    if not -20 <= nice <= 19:
        raise ValueError(f"nice must be -20..19, got {nice}")
    try:
        backend.renice(pid, nice)
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError) as exc:
        return ActionResult(ok=False, message="", error=_from_oserror(exc))
    return ActionResult(ok=True, message=f"renice pid {pid} → {nice}")


__all__ = [
    "ActionResult",
    "kill_pid",
    "kill_scope",
    "renice",
    "set_cpu_weight",
    "set_memory_high",
    "set_memory_max",
]
