"""Tests for `azrael.control.applier.apply_caps`."""

from __future__ import annotations

from dataclasses import dataclass, field

from azrael.agents.descriptor import Caps
from azrael.control.actions import ActionResult
from azrael.control.applier import apply_caps
from azrael.platforms._common import (
    CAP_CPU_WEIGHT,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    CAP_SENSOR,
    Capabilities,
    Scope,
)


@dataclass
class FakeBackend:
    name: str = "fake"
    capabilities: Capabilities = field(
        default_factory=lambda: frozenset(
            {CAP_CPU_WEIGHT, CAP_MEMORY_MAX, CAP_MEMORY_HIGH, CAP_SENSOR}
        )
    )
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        self.calls.append(("set_cpu_weight", (scope, weight)))

    def set_memory_max(self, scope: Scope, bytes: int) -> None:
        self.calls.append(("set_memory_max", (scope, bytes)))

    def set_memory_high(self, scope: Scope, bytes: int) -> None:
        self.calls.append(("set_memory_high", (scope, bytes)))


_SCOPE = Scope(backend_name="fake", path="/x.scope", leader_pid=None)


class TestApplyCaps:
    def test_apply_caps_with_full_support(self) -> None:
        b = FakeBackend()
        results = apply_caps(
            b,
            _SCOPE,
            Caps(cpu_weight=200, memory_max=4 * 1024**3, memory_high=2 * 1024**3),
        )
        assert len(results) == 3
        assert all(r.ok for r in results)
        assert [c[0] for c in b.calls] == ["set_cpu_weight", "set_memory_max", "set_memory_high"]

    def test_apply_caps_skips_unsupported(self) -> None:
        # Drop CAP_MEMORY_HIGH.
        b = FakeBackend(capabilities=frozenset({CAP_CPU_WEIGHT, CAP_MEMORY_MAX, CAP_SENSOR}))
        results = apply_caps(
            b,
            _SCOPE,
            Caps(cpu_weight=100, memory_max=1024**3, memory_high=512 * 1024**2),
        )
        assert len(results) == 3
        ok_count = sum(1 for r in results if r.ok)
        err_count = sum(1 for r in results if not r.ok)
        assert ok_count == 2
        assert err_count == 1
        assert any(r.error is not None and CAP_MEMORY_HIGH in r.error for r in results)
        # Only two backend calls; memory_high was not invoked.
        assert [c[0] for c in b.calls] == ["set_cpu_weight", "set_memory_max"]

    def test_apply_caps_empty_caps_returns_empty_tuple(self) -> None:
        b = FakeBackend()
        assert apply_caps(b, _SCOPE, Caps()) == ()
        assert b.calls == []

    def test_apply_caps_error_propagates(self) -> None:
        """Backend PermissionError becomes ActionResult(ok=False)."""

        @dataclass
        class PermBackend:
            name: str = "fake"
            capabilities: Capabilities = field(
                default_factory=lambda: frozenset({CAP_CPU_WEIGHT, CAP_MEMORY_MAX})
            )

            def set_cpu_weight(self, scope: Scope, weight: int) -> None:
                raise PermissionError(1, "Operation not permitted")

            def set_memory_max(self, scope: Scope, bytes: int) -> None:
                return None

            def set_memory_high(self, scope: Scope, bytes: int) -> None:
                return None

        b = PermBackend()
        results = apply_caps(b, _SCOPE, Caps(cpu_weight=100))
        assert len(results) == 1
        assert results[0].ok is False
        assert isinstance(results[0], ActionResult)
        assert results[0].error is not None and "permission" in results[0].error.lower()
