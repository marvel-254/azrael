from __future__ import annotations

import contextlib
import errno
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from azrael.platforms._common import (
    CAP_CPU_QUOTA,
    CAP_CPU_WEIGHT,
    CAP_KILL_SCOPE,
    CAP_MEMORY_HIGH,
    CAP_MEMORY_MAX,
    CAP_SENSOR,
    Capabilities,
    ProcessMetrics,
    Scope,
    ScopeMetrics,
)

if TYPE_CHECKING:
    from azrael.agents.descriptor import AgentDescriptor


class LinuxCgroupV2Backend:
    name: str = "linux_cgroup_v2"
    capabilities: Capabilities = frozenset(
        {
            CAP_CPU_WEIGHT,
            CAP_MEMORY_MAX,
            CAP_MEMORY_HIGH,
            CAP_SENSOR,
            CAP_KILL_SCOPE,
            CAP_CPU_QUOTA,
        }
    )

    def __init__(
        self,
        cgroup_root: str = "/sys/fs/cgroup",
        proc_root: str = "/proc",
    ) -> None:
        self.cgroup_root: str = cgroup_root
        self.proc_root: str = proc_root

    def discover_scopes(self) -> list[Scope]:
        out: list[Scope] = []
        base = Path(self.cgroup_root) / "user.slice"
        if not base.is_dir():
            return []
        for root, dirs, _files in os.walk(base):
            for d in dirs:
                if d.endswith(".scope"):
                    out.append(Scope(self.name, str(Path(root) / d), None))
        out.sort(key=lambda s: s.path)
        return out

    def read_scope_metrics(self, scope: Scope) -> ScopeMetrics:
        base = Path(scope.path)
        quota, period = self._read_cpu_max(base)
        cpu_stat = self._read_cpu_stat(base)
        mem_cur, mem_max, mem_high, mem_low = self._read_memory(base)
        oom_kill = self._read_memory_events(base)
        pressure = self._read_memory_pressure(base)
        pids = self._read_pids(base)
        weight = self._read_cpu_weight(base)
        return ScopeMetrics(
            pids=pids,
            cpu_usage_usec=cpu_stat.get("usage_usec", 0),
            cpu_quota_usec=quota,
            cpu_period_usec=period,
            cpu_weight=weight,
            nr_periods=cpu_stat.get("nr_periods", 0),
            nr_throttled=cpu_stat.get("nr_throttled", 0),
            throttled_usec=cpu_stat.get("throttled_usec", 0),
            mem_cur=mem_cur,
            mem_max=mem_max,
            mem_high=mem_high,
            mem_low=mem_low,
            mem_pressure_avg10=pressure,
            oom_kill=oom_kill,
        )

    def _read_cpu_max(self, base: Path) -> tuple[int, int]:
        try:
            parts = (base / "cpu.max").read_text().split()
            quota = 0 if parts[0] == "max" else int(parts[0])
            period = int(parts[1]) if len(parts) > 1 else 100000
            return quota, period
        except (OSError, ValueError, IndexError):
            return (0, 100000)

    def _read_cpu_stat(self, base: Path) -> dict[str, int]:
        wanted = {
            "usage_usec",
            "user_usec",
            "system_usec",
            "nr_periods",
            "nr_throttled",
            "throttled_usec",
        }
        out: dict[str, int] = {}
        try:
            text = (base / "cpu.stat").read_text()
        except OSError:
            return out
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] in wanted:
                try:
                    out[parts[0]] = int(parts[1])
                except ValueError:
                    continue
        return out

    def _read_cpu_weight(self, base: Path) -> int:
        try:
            return int((base / "cpu.weight").read_text().strip())
        except (OSError, ValueError):
            return 100

    def _read_memory(self, base: Path) -> tuple[int, int | None, int | None, int | None]:
        def read_int_opt(name: str) -> int | None:
            try:
                text = (base / name).read_text().strip()
            except OSError:
                return None
            if text == "max" or text == "":
                return None
            try:
                return int(text)
            except ValueError:
                return None

        cur = read_int_opt("memory.current")
        mx = read_int_opt("memory.max")
        high = read_int_opt("memory.high")
        low = read_int_opt("memory.low")
        return (cur or 0, mx, high, low)

    def _read_memory_events(self, base: Path) -> int:
        try:
            text = (base / "memory.events").read_text()
        except OSError:
            return 0
        for line in text.splitlines():
            if line.startswith("oom_kill "):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        return 0
        return 0

    def _read_memory_pressure(self, base: Path) -> float:
        try:
            text = (base / "memory.pressure").read_text()
        except OSError:
            return 0.0
        first_line = text.splitlines()[0] if text else ""
        for part in first_line.split():
            if part.startswith("avg10="):
                try:
                    return float(part[len("avg10=") :])
                except ValueError:
                    return 0.0
        return 0.0

    def _read_pids(self, base: Path) -> tuple[int, ...]:
        try:
            text = (base / "cgroup.procs").read_text()
        except OSError:
            return ()
        out: list[int] = []
        for line in text.splitlines():
            s = line.strip()
            if s.isdigit():
                out.append(int(s))
        return tuple(out)

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        if not 1 <= weight <= 10000:
            raise ValueError(f"cpu.weight must be 1..10000, got {weight}")
        path = Path(scope.path) / "cpu.weight"
        if not path.exists():
            raise FileNotFoundError(
                f"no cpu.weight under {scope.path} (loose process has no cgroup cap)"
            )
        path.write_text(f"{weight}\n")

    def set_memory_max(self, scope: Scope, bytes: int) -> None:
        if bytes < 0:
            raise ValueError(f"memory.max must be >= 0, got {bytes}")
        path = Path(scope.path) / "memory.max"
        if not path.exists():
            raise FileNotFoundError(
                f"no memory.max under {scope.path} (loose process has no cgroup cap)"
            )
        path.write_text(f"{bytes}\n")

    def set_memory_high(self, scope: Scope, bytes: int) -> None:
        if bytes < 0:
            raise ValueError(f"memory.high must be >= 0, got {bytes}")
        path = Path(scope.path) / "memory.high"
        if not path.exists():
            raise FileNotFoundError(
                f"no memory.high under {scope.path} (loose process has no cgroup cap)"
            )
        path.write_text(f"{bytes}\n")

    def kill_scope(self, scope: Scope) -> None:
        unit = Path(scope.path).name
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", unit],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            raise

    def install_sensor(
        self,
        agent_descriptor: AgentDescriptor,
        cmd: list[str],
    ) -> Scope:
        if agent_descriptor.sensor_template is None:
            raise ValueError(f"agent {agent_descriptor.key!r} has no sensor_template")
        template = agent_descriptor.sensor_template.format(
            key=agent_descriptor.key, cmd=" ".join(cmd)
        )
        subprocess.run(
            ["bash", "-c", template],
            check=True,
            capture_output=True,
        )
        placeholder_path = (
            f"{self.cgroup_root}/user.slice/azrael-{agent_descriptor.key}-<leader>.scope"
        )
        return Scope(self.name, placeholder_path, None)

    def remove_sensor(self, scope: Scope) -> None:
        self.kill_scope(scope)

    def discover_loose(self) -> dict[int, AgentDescriptor]:
        # TODO Phase 4: wire up to Registry via cmdline scan.
        return {}

    def read_process_metrics(self, pid: int) -> ProcessMetrics:
        base = Path(self.proc_root) / str(pid)
        cmd = self._read_proc_cmdline(base)
        state, utime, stime, nice, ppid = self._read_proc_stat(base)
        rss, threads = self._read_proc_status(base)
        rchar, wchar = self._read_proc_io(base)
        return ProcessMetrics(
            pid=pid,
            ppid=ppid,
            cmd=cmd,
            state=state,
            nice=nice,
            cpu_ticks=utime + stime,
            cpu_pct=0.0,
            mem_rss=rss,
            threads=threads,
            io_rchar=rchar,
            io_wchar=wchar,
            io_rd_rate=0.0,
            io_wr_rate=0.0,
        )

    def _read_proc_cmdline(self, base: Path) -> str:
        try:
            raw = base.joinpath("cmdline").read_bytes()
        except OSError:
            return ""
        return raw.decode("utf-8", errors="replace").replace("\x00", " ").strip()

    def _read_proc_stat(
        self,
        base: Path,
    ) -> tuple[str, int, int, int, int]:
        try:
            text = (base / "stat").read_text()
        except OSError:
            return ("?", 0, 0, 0, 0)
        close = text.rfind(")")
        if close < 0:
            return ("?", 0, 0, 0, 0)
        rest = text[close + 1 :].split()
        state = rest[0] if rest else "?"
        ppid = _safe_int(rest, 1, 0)
        nice = _safe_int(rest, 16, 0)
        utime = _safe_int(rest, 11, 0)
        stime = _safe_int(rest, 12, 0)
        return (state, utime, stime, nice, ppid)

    def _read_proc_status(self, base: Path) -> tuple[int, int]:
        rss = 0
        threads = 1
        try:
            text = (base / "status").read_text()
        except OSError:
            return (rss, threads)
        for line in text.splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        rss = int(parts[1]) * 1024
            elif line.startswith("Threads:"):
                parts = line.split()
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        threads = int(parts[1])
        return (rss, threads)

    def _read_proc_io(self, base: Path) -> tuple[int, int]:
        rchar = 0
        wchar = 0
        try:
            text = (base / "io").read_text()
        except OSError:
            return (rchar, wchar)
        for line in text.splitlines():
            if line.startswith("rchar:"):
                parts = line.split()
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        rchar = int(parts[1])
            elif line.startswith("wchar:"):
                parts = line.split()
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        wchar = int(parts[1])
        return (rchar, wchar)

    def kill_pid(self, pid: int, sig: int = 15) -> None:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            raise
        except OSError as exc:
            raise OSError(exc.errno or errno.EIO, exc.strerror or str(exc)) from exc

    def renice(self, pid: int, nice: int) -> None:
        if not -20 <= nice <= 19:
            raise ValueError(f"nice must be -20..19, got {nice}")
        try:
            os.setpriority(os.PRIO_PROCESS, pid, nice)
        except (ProcessLookupError, PermissionError):
            raise
        except OSError as exc:
            raise OSError(exc.errno or errno.EIO, exc.strerror or str(exc)) from exc


def _safe_int(parts: list[str], idx: int, default: int) -> int:
    try:
        return int(parts[idx])
    except (IndexError, ValueError):
        return default


__all__ = ["LinuxCgroupV2Backend"]
