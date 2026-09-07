from __future__ import annotations

import errno
import os
import signal
from pathlib import Path
from unittest.mock import patch

import pytest

from azrael.platforms._common import (
    CAP_CPU_QUOTA,
    CAP_CPU_WEIGHT,
    CAP_KILL_SCOPE,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    CAP_SENSOR,
    Scope,
)
from azrael.platforms.linux_cgroup_v2 import LinuxCgroupV2Backend
from tests.platforms.conftest import make_proc, make_scope


def test_discover_scopes_finds_scope_dirs(cgroup_root: Path) -> None:
    make_scope(cgroup_root, "opencode-1234.scope", {"cgroup.procs": ""})
    make_scope(cgroup_root, "hermes-99.scope", {"cgroup.procs": ""})
    (cgroup_root / "user.slice" / "not-a-scope").mkdir()
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    scopes = b.discover_scopes()
    names = sorted(Path(s.path).name for s in scopes)
    assert names == ["hermes-99.scope", "opencode-1234.scope"]


def test_discover_scopes_finds_nested_scopes(cgroup_root: Path) -> None:
    sub = cgroup_root / "user.slice" / "sub"
    sub.mkdir()
    make_scope(cgroup_root, "opencode-1.scope", {"cgroup.procs": ""}, parent="user.slice/sub")
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    scopes = b.discover_scopes()
    assert any(s.path.endswith("opencode-1.scope") for s in scopes)


def test_discover_scopes_empty_user_slice(cgroup_root: Path) -> None:
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    assert b.discover_scopes() == []


def test_discover_scopes_returns_sorted(cgroup_root: Path) -> None:
    make_scope(cgroup_root, "zeta-1.scope", {"cgroup.procs": ""})
    make_scope(cgroup_root, "alpha-1.scope", {"cgroup.procs": ""})
    make_scope(cgroup_root, "beta-1.scope", {"cgroup.procs": ""})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    names = [Path(s.path).name for s in b.discover_scopes()]
    assert names == sorted(names)


def test_read_scope_metrics_cpu_max_unlimited(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"cpu.max": "max 100000\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.cpu_quota_usec == 0
    assert m.cpu_period_usec == 100000


def test_read_scope_metrics_cpu_max_limited(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"cpu.max": "200000 100000\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.cpu_quota_usec == 200000
    assert m.cpu_period_usec == 100000


def test_read_scope_metrics_cpu_stat_all_fields(cgroup_root: Path) -> None:
    cpu_stat = (
        "usage_usec 123456789\n"
        "user_usec 100000\n"
        "system_usec 200000\n"
        "nr_periods 50\n"
        "nr_throttled 7\n"
        "throttled_usec 999\n"
    )
    p = make_scope(cgroup_root, "x-1.scope", {"cpu.stat": cpu_stat})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.cpu_usage_usec == 123456789
    assert m.nr_periods == 50
    assert m.nr_throttled == 7
    assert m.throttled_usec == 999


def test_read_scope_metrics_memory_current_max_high(cgroup_root: Path) -> None:
    files = {
        "memory.current": "1073741824\n",
        "memory.max": "2147483648\n",
        "memory.high": "3221225472\n",
    }
    p = make_scope(cgroup_root, "x-1.scope", files)
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.mem_cur == 1073741824
    assert m.mem_max == 2147483648
    assert m.mem_high == 3221225472


def test_read_scope_metrics_memory_max_unlimited(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"memory.max": "max\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.mem_max is None


def test_read_scope_metrics_memory_pressure_avg10(cgroup_root: Path) -> None:
    p = make_scope(
        cgroup_root,
        "x-1.scope",
        {"memory.pressure": "some avg10=5.23 avg60=1.00 avg300=0.50 total=1234\nfull avg10=0.00\n"},
    )
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.mem_pressure_avg10 == pytest.approx(5.23)


def test_read_scope_metrics_memory_events_oom(cgroup_root: Path) -> None:
    p = make_scope(
        cgroup_root,
        "x-1.scope",
        {"memory.events": "low 0\nhigh 0\nmax 0\noom 0\noom_kill 3\n"},
    )
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.oom_kill == 3


def test_read_scope_metrics_pids_from_cgroup_procs(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"cgroup.procs": "111\n222\n333\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.pids == (111, 222, 333)


def test_read_scope_metrics_default_cpu_weight_100(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {})  # no cpu.weight file
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.cpu_weight == 100


def test_read_scope_metrics_handles_missing_files(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    m = b.read_scope_metrics(Scope(b.name, str(p), None))
    assert m.cpu_usage_usec == 0
    assert m.mem_cur == 0
    assert m.mem_max is None
    assert m.pids == ()


def test_set_cpu_weight_writes_file(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"cpu.weight": "100\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    b.set_cpu_weight(Scope(b.name, str(p), None), 200)
    assert (p / "cpu.weight").read_text() == "200\n"


def test_set_cpu_weight_validates_range(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"cpu.weight": "100\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    scope = Scope(b.name, str(p), None)
    with pytest.raises(ValueError):
        b.set_cpu_weight(scope, 0)
    with pytest.raises(ValueError):
        b.set_cpu_weight(scope, 10001)


def test_set_cpu_weight_missing_file_raises(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {})  # no cpu.weight file
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    with pytest.raises(FileNotFoundError):
        b.set_cpu_weight(Scope(b.name, str(p), None), 200)


def test_set_memory_max_writes_file(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"memory.max": "max\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    b.set_memory_max(Scope(b.name, str(p), None), 4 * 1024**3)
    assert (p / "memory.max").read_text() == f"{4 * 1024**3}\n"


def test_set_memory_high_writes_file(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"memory.high": "max\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    b.set_memory_high(Scope(b.name, str(p), None), 2 * 1024**3)
    assert (p / "memory.high").read_text() == f"{2 * 1024**3}\n"


def test_set_memory_max_validates_non_negative(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {"memory.max": "max\n"})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    with pytest.raises(ValueError):
        b.set_memory_max(Scope(b.name, str(p), None), -1)


def test_set_memory_high_missing_file_raises(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "x-1.scope", {})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    with pytest.raises(FileNotFoundError):
        b.set_memory_high(Scope(b.name, str(p), None), 100)


def test_kill_scope_invokes_systemctl(cgroup_root: Path) -> None:
    p = make_scope(cgroup_root, "opencode-1234.scope", {})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    scope = Scope(b.name, str(p), None)
    with patch("azrael.platforms.linux_cgroup_v2.subprocess.run") as mock_run:
        b.kill_scope(scope)
    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert args == ["systemctl", "--user", "stop", "opencode-1234.scope"]


def test_kill_scope_translates_called_process_error(cgroup_root: Path) -> None:
    import subprocess

    p = make_scope(cgroup_root, "opencode-1234.scope", {})
    b = LinuxCgroupV2Backend(cgroup_root=str(cgroup_root))
    scope = Scope(b.name, str(p), None)
    err = subprocess.CalledProcessError(1, ["x"], stderr=b"boom")
    with (
        patch(
            "azrael.platforms.linux_cgroup_v2.subprocess.run",
            side_effect=err,
        ),
        pytest.raises(subprocess.CalledProcessError) as ei,
    ):
        b.kill_scope(scope)
    assert ei.value is err


def test_kill_pid_translates_errors() -> None:
    b = LinuxCgroupV2Backend()
    with (
        patch("azrael.platforms.linux_cgroup_v2.os.kill", side_effect=ProcessLookupError),
        pytest.raises(ProcessLookupError),
    ):
        b.kill_pid(99999)
    with (
        patch("azrael.platforms.linux_cgroup_v2.os.kill", side_effect=PermissionError),
        pytest.raises(PermissionError),
    ):
        b.kill_pid(1)
    with (
        patch(
            "azrael.platforms.linux_cgroup_v2.os.kill",
            side_effect=OSError(errno.EINTR, "intr"),
        ),
        pytest.raises(OSError) as ei,
    ):
        b.kill_pid(1)
    assert ei.value.errno == errno.EINTR


def test_kill_pid_invokes_kill() -> None:
    b = LinuxCgroupV2Backend()
    with patch("azrael.platforms.linux_cgroup_v2.os.kill") as mk:
        b.kill_pid(123, sig=signal.SIGTERM)
    mk.assert_called_once_with(123, signal.SIGTERM)


def test_renice_validates_range() -> None:
    b = LinuxCgroupV2Backend()
    with pytest.raises(ValueError):
        b.renice(1, -21)
    with pytest.raises(ValueError):
        b.renice(1, 20)


def test_renice_invokes_setpriority() -> None:
    b = LinuxCgroupV2Backend()
    with patch("azrael.platforms.linux_cgroup_v2.os.setpriority") as mp:
        b.renice(123, 5)
    mp.assert_called_once_with(os.PRIO_PROCESS, 123, 5)


def test_renice_translates_errors() -> None:
    b = LinuxCgroupV2Backend()
    with (
        patch("azrael.platforms.linux_cgroup_v2.os.setpriority", side_effect=PermissionError),
        pytest.raises(PermissionError),
    ):
        b.renice(1, 5)


def test_read_process_metrics_parses_stat_with_parens(proc_root: Path) -> None:
    # Process name contains '(' and ')' - exercise the split-after-last-paren path.
    # Comm contains '(' and ')'; verify split-after-last-paren path.
    # After "(comm)": rest[0]=state(3), rest[1]=ppid(4), rest[11]=utime(14),
    # rest[12]=stime(15), rest[16]=nice(19).
    stat = "1 (weird) name) S 1 1 1 0 -1 1 0 0 0 0 100 200 0 0 0 -5 1 0 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0\n"
    make_proc(proc_root, 1, cmdline="weird name --foo", stat=stat)
    b = LinuxCgroupV2Backend(proc_root=str(proc_root))
    m = b.read_process_metrics(1)
    assert m.state == "S"
    assert m.pid == 1
    assert m.ppid == 1
    assert m.nice == -5
    assert m.cpu_ticks == 300


def test_read_process_metrics_parses_io(proc_root: Path) -> None:
    io = "rchar: 12345\nwchar: 67890\nsyscr: 100\nsyscw: 50\nread_bytes: 0\nwrite_bytes: 0\n"
    make_proc(
        proc_root,
        2,
        cmdline="x",
        stat="2 (x) S 0 1 1 0 -1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0\n",
        io=io,
    )
    b = LinuxCgroupV2Backend(proc_root=str(proc_root))
    m = b.read_process_metrics(2)
    assert m.io_rchar == 12345
    assert m.io_wchar == 67890


def test_read_process_metrics_parses_status_rss_and_threads(proc_root: Path) -> None:
    status = "Name: x\nVmRSS:\t4096 kB\nThreads:\t8\n"
    make_proc(
        proc_root,
        3,
        cmdline="x",
        stat="3 (x) S 0 1 1 0 -1 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0\n",
        status=status,
    )
    b = LinuxCgroupV2Backend(proc_root=str(proc_root))
    m = b.read_process_metrics(3)
    assert m.mem_rss == 4096 * 1024
    assert m.threads == 8


def test_read_process_metrics_handles_missing_pid(proc_root: Path) -> None:
    b = LinuxCgroupV2Backend(proc_root=str(proc_root))
    m = b.read_process_metrics(99999)
    assert m.pid == 99999
    assert m.cmd == ""
    assert m.state == "?"


def test_capabilities_includes_expected_keys() -> None:
    b = LinuxCgroupV2Backend()
    assert CAP_CPU_WEIGHT in b.capabilities
    assert CAP_MEMORY_MAX in b.capabilities
    assert CAP_MEMORY_HIGH in b.capabilities
    assert CAP_SENSOR in b.capabilities
    assert CAP_KILL_SCOPE in b.capabilities
    assert CAP_CPU_QUOTA in b.capabilities


def test_discover_loose_returns_empty_for_phase3() -> None:
    b = LinuxCgroupV2Backend()
    assert b.discover_loose() == {}


def test_install_sensor_returns_placeholder(tmp_path: Path) -> None:
    from azrael.agents.descriptor import AgentDescriptor

    b = LinuxCgroupV2Backend(cgroup_root=str(tmp_path / "cgroup"))
    d = AgentDescriptor(
        key="x",
        display_name="X",
        cmdline_needles=("x",),
        scope_fragments=("x", ".scope"),
        sensor_template="systemd-run --user --scope --unit=azrael-{key} {cmd}",
    )
    with patch("azrael.platforms.linux_cgroup_v2.subprocess.run") as mr:
        scope = b.install_sensor(d, ["sleep", "1"])
    # subprocess.run called with bash -c and the rendered template
    assert mr.called
    args = mr.call_args.args[0]
    assert args[0] == "bash"
    assert args[1] == "-c"
    assert "{key}" not in args[2]
    assert "x" in args[2]
    assert "sleep 1" in args[2]
    # placeholder scope returned
    assert isinstance(scope, Scope)
    assert scope.backend_name == b.name
