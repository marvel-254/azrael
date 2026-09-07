"""Tests for `azrael.control.actions` — wraps a fake ResourceBackend."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from azrael.control.actions import (
    ActionResult,
    kill_pid,
    kill_scope,
    renice,
    set_cpu_weight,
    set_memory_high,
    set_memory_max,
)
from azrael.platforms._common import (
    CAP_CPU_WEIGHT,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    CAP_SENSOR,
    Capabilities,
    Scope,
)


@dataclass
class _Call:
    name: str
    args: tuple[object, ...]


@dataclass
class FakeBackend:
    name: str = "fake"
    capabilities: Capabilities = field(
        default_factory=lambda: frozenset(
            {CAP_CPU_WEIGHT, CAP_MEMORY_MAX, CAP_MEMORY_HIGH, CAP_SENSOR}
        )
    )
    calls: list[_Call] = field(default_factory=list)

    # Configurable per-method side effects (set in tests as needed).
    raise_process: Exception | None = None
    raise_permission: Exception | None = None
    raise_not_found: Exception | None = None
    raise_subprocess: Exception | None = None

    def _maybe_raise(self) -> None:
        if self.raise_process is not None:
            exc, self.raise_process = self.raise_process, None
            raise exc
        if self.raise_permission is not None:
            exc, self.raise_permission = self.raise_permission, None
            raise exc
        if self.raise_not_found is not None:
            exc, self.raise_not_found = self.raise_not_found, None
            raise exc
        if self.raise_subprocess is not None:
            exc, self.raise_subprocess = self.raise_subprocess, None
            raise exc

    def kill_pid(self, pid: int, sig: int = 15) -> None:
        self.calls.append(_Call("kill_pid", (pid, sig)))
        self._maybe_raise()

    def kill_scope(self, scope: Scope) -> None:
        self.calls.append(_Call("kill_scope", (scope,)))
        self._maybe_raise()

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        self.calls.append(_Call("set_cpu_weight", (scope, weight)))
        self._maybe_raise()

    def set_memory_max(self, scope: Scope, bytes: int) -> None:
        self.calls.append(_Call("set_memory_max", (scope, bytes)))
        self._maybe_raise()

    def set_memory_high(self, scope: Scope, bytes: int) -> None:
        self.calls.append(_Call("set_memory_high", (scope, bytes)))
        self._maybe_raise()

    def renice(self, pid: int, nice: int) -> None:
        self.calls.append(_Call("renice", (pid, nice)))
        self._maybe_raise()


_SCOPE = Scope(backend_name="fake", path="/tmp/fake.scope", leader_pid=None)


class TestKillPid:
    def test_kill_pid_success(self) -> None:
        b = FakeBackend()
        r = kill_pid(b, 1234, 15)
        assert r.ok is True
        assert b.calls == [_Call("kill_pid", (1234, 15))]

    def test_kill_pid_process_not_found(self) -> None:
        b = FakeBackend(raise_process=ProcessLookupError(3, "No such process"))
        r = kill_pid(b, 9999)
        assert r.ok is False
        assert r.error is not None and "process gone" in r.error.lower()

    def test_kill_pid_permission_denied(self) -> None:
        b = FakeBackend(raise_permission=PermissionError(1, "Operation not permitted"))
        r = kill_pid(b, 1)
        assert r.ok is False
        assert r.error is not None and "permission" in r.error.lower()

    def test_kill_pid_invalid_pid_raises(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            kill_pid(b, 0)

    def test_kill_pid_invalid_signal_raises(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            kill_pid(b, 1, 99)


class TestKillScope:
    def test_kill_scope_invokes_backend(self) -> None:
        b = FakeBackend()
        r = kill_scope(b, _SCOPE)
        assert r.ok is True
        assert b.calls == [_Call("kill_scope", (_SCOPE,))]

    def test_kill_scope_permission_denied(self) -> None:
        b = FakeBackend(raise_permission=PermissionError(1, "denied"))
        r = kill_scope(b, _SCOPE)
        assert r.ok is False
        assert r.error is not None

    def test_kill_scope_invalid_path_raises(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            kill_scope(b, Scope("fake", "", None))


class TestSetCpuWeight:
    def test_set_cpu_weight_success(self) -> None:
        b = FakeBackend()
        r = set_cpu_weight(b, _SCOPE, 200)
        assert r.ok is True
        assert b.calls == [_Call("set_cpu_weight", (_SCOPE, 200))]

    def test_set_cpu_weight_validates_range(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            set_cpu_weight(b, _SCOPE, 0)
        with pytest.raises(ValueError):
            set_cpu_weight(b, _SCOPE, 10001)
        assert b.calls == []


class TestSetMemoryMax:
    def test_set_memory_max_success(self) -> None:
        b = FakeBackend()
        r = set_memory_max(b, _SCOPE, 1024 * 1024)
        assert r.ok is True
        assert b.calls == [_Call("set_memory_max", (_SCOPE, 1024 * 1024))]

    def test_set_memory_max_unlimited_sends_negative_sentinel_or_max_string(self) -> None:
        """`None` (unlimited) is translated to the unlimited sentinel ``-1``;
        the cgroup v2 backend writes ``"max\\n"`` for any negative byte
        count. This locks the convention: actions.send ``-1`` means unlimited.
        """
        b = FakeBackend()
        r = set_memory_max(b, _SCOPE, None)
        assert r.ok is True
        assert b.calls == [_Call("set_memory_max", (_SCOPE, -1))]
        assert r.message is not None and "unlimited" in r.message.lower()

    def test_set_memory_max_invalid_raises(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            set_memory_max(b, _SCOPE, -5)
        assert b.calls == []


class TestSetMemoryHigh:
    def test_set_memory_high_success(self) -> None:
        b = FakeBackend()
        r = set_memory_high(b, _SCOPE, 512 * 1024 * 1024)
        assert r.ok is True
        assert b.calls == [_Call("set_memory_high", (_SCOPE, 512 * 1024 * 1024))]

    def test_set_memory_high_unlimited(self) -> None:
        b = FakeBackend()
        r = set_memory_high(b, _SCOPE, None)
        assert r.ok is True
        assert b.calls == [_Call("set_memory_high", (_SCOPE, -1))]


class TestRenice:
    def test_renice_success(self) -> None:
        b = FakeBackend()
        r = renice(b, 42, 5)
        assert r.ok is True
        assert b.calls == [_Call("renice", (42, 5))]

    def test_renice_validates_range(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            renice(b, 42, -21)
        with pytest.raises(ValueError):
            renice(b, 42, 20)
        assert b.calls == []

    def test_renice_invalid_pid_raises(self) -> None:
        b = FakeBackend()
        with pytest.raises(ValueError):
            renice(b, 0, 5)
        assert b.calls == []


def test_action_result_is_frozen() -> None:
    r = ActionResult(ok=True, message="hi")
    with pytest.raises((AttributeError, Exception)):
        r.ok = False  # type: ignore[misc]
