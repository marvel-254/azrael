from __future__ import annotations

from pathlib import Path

import pytest

from azrael.platforms.backend import ResourceBackend, detect
from azrael.platforms.linux_cgroup_v2 import LinuxCgroupV2Backend


def test_detect_returns_linux_backend_when_cgroup_exists(tmp_path: Path) -> None:
    root = tmp_path / "cgroup"
    root.mkdir()
    (root / "user.slice").mkdir()
    backend = detect(cgroup_root=str(root))
    assert isinstance(backend, LinuxCgroupV2Backend)


def test_detect_raises_when_no_cgroup(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no ResourceBackend"):
        detect(cgroup_root=str(tmp_path / "missing"))


def test_protocol_accepts_linux_backend(tmp_path: Path) -> None:
    backend = LinuxCgroupV2Backend(cgroup_root=str(tmp_path / "cgroup"))
    # structural check; isinstance with Protocol works if decorated with runtime
    assert hasattr(backend, "name")
    assert hasattr(backend, "capabilities")
    assert hasattr(backend, "discover_scopes")
    assert hasattr(backend, "read_scope_metrics")
    assert hasattr(backend, "kill_pid")
    assert hasattr(backend, "renice")
    # explicit cast via isinstance works for Protocol with only method attrs
    # when accessed structurally; the type system already enforces this.
    _: ResourceBackend = backend
