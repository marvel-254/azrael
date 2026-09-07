from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def cgroup_root(tmp_path: Path) -> Path:
    root = tmp_path / "cgroup"
    (root / "user.slice").mkdir(parents=True)
    return root


@pytest.fixture
def proc_root(tmp_path: Path) -> Path:
    return tmp_path / "proc"


def make_scope(
    root: Path,
    name: str,
    files: dict[str, str],
    parent: str = "user.slice",
) -> Path:
    scope = root / parent / name
    scope.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (scope / fname).write_text(content)
    return scope


def make_proc(
    root: Path,
    pid: int,
    *,
    cmdline: str = "",
    stat: str = "",
    status: str = "",
    io: str = "",
) -> None:
    proc = root / str(pid)
    proc.mkdir(parents=True, exist_ok=True)
    if cmdline:
        (proc / "cmdline").write_bytes(cmdline.encode("utf-8") + b"\x00")
    if stat:
        (proc / "stat").write_text(stat)
    if status:
        (proc / "status").write_text(status)
    if io:
        (proc / "io").write_text(io)
