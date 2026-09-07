"""Install / list / remove sensors (systemd --user scope wrappers).

Phase 6 ships:

- ``install_sensor`` — invokes ``systemd-run`` with cap properties.
- ``list_sensors`` — enumerates active ``azrael-*.scope`` units.
- ``remove_sensor`` / ``set_sensor_caps`` — stubs for Phase 7.

Sensors are persisted to disk in Phase 7; for now `Sensor.persistent`
is just a flag the install layer accepts but doesn't act on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from azrael.agents.descriptor import Caps
from azrael.platforms._common import CAP_SENSOR
from azrael.platforms.backend import ResourceBackend

if TYPE_CHECKING:
    from azrael.agents.descriptor import AgentDescriptor

_OOM_POLICIES = ("kill", "stop", "continue")
_MODES = ("monitor-only", "control")

_AZRAEL_PREFIX = "azrael-"


@dataclass(frozen=True)
class Sensor:
    agent_key: str
    scope_path: str
    pid: int
    mode: Literal["monitor-only", "control"]
    caps: Caps
    oom_policy: Literal["kill", "stop", "continue"]
    persistent: bool
    installed_at: datetime
    systemd_unit_path: Path | None


def _build_systemd_argv(
    descriptor: AgentDescriptor,
    cmd: list[str],
    caps: Caps,
    oom_policy: str,
) -> list[str]:
    unit_name = f"{_AZRAEL_PREFIX}{descriptor.key}"
    argv: list[str] = ["systemd-run", "--user", "--scope", f"--unit={unit_name}"]
    if caps.cpu_weight is not None:
        argv.append(f"--property=CPUWeight={caps.cpu_weight}")
    if caps.memory_max is not None:
        argv.append(f"--property=MemoryMax={caps.memory_max}")
    if caps.memory_high is not None:
        argv.append(f"--property=MemoryHigh={caps.memory_high}")
    if oom_policy != "continue":
        argv.append(f"--property=MemoryOOMPolicy={oom_policy}")
    argv.extend(cmd)
    return argv


_DEFAULT_CAPS = Caps()


def install_sensor(
    backend: ResourceBackend,
    descriptor: AgentDescriptor,
    cmd: list[str],
    *,
    mode: Literal["monitor-only", "control"] = "control",
    caps: Caps = _DEFAULT_CAPS,
    oom_policy: Literal["kill", "stop", "continue"] = "continue",
    persistent: bool = False,
) -> Sensor:
    """Install a systemd --user scope wrapping ``cmd``.

    Runs ``systemd-run --user --scope --unit=azrael-<key>`` with the
    cap properties derived from ``caps``. Does not persist to disk —
    that's Phase 7.

    Raises:
        RuntimeError: if the backend doesn't advertise ``CAP_SENSOR``.
        FileNotFoundError: if ``systemd-run`` is not on ``PATH``.
        subprocess.CalledProcessError: if ``systemd-run`` exits non-zero.
        ValueError: on bad ``mode`` / ``oom_policy`` / ``cmd``.
    """
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}, got {mode!r}")
    if oom_policy not in _OOM_POLICIES:
        raise ValueError(f"oom_policy must be one of {_OOM_POLICIES}, got {oom_policy!r}")
    if not cmd:
        raise ValueError("cmd must be a non-empty list")
    if CAP_SENSOR not in backend.capabilities:
        raise RuntimeError(
            f"backend {backend.name!r} does not advertise capability {CAP_SENSOR!r}; "
            "sensor install is not supported on this platform"
        )

    argv = _build_systemd_argv(descriptor, cmd, caps, oom_policy)
    try:
        proc = subprocess.run(argv, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        raise subprocess.CalledProcessError(
            exc.returncode, exc.cmd, output=exc.output, stderr=stderr
        ) from exc

    unit_name = f"{_AZRAEL_PREFIX}{descriptor.key}"
    scope_name = f"{unit_name}.scope"
    scope_path = (
        f"/sys/fs/cgroup/user.slice/{scope_name}"
        if backend.name == "linux_cgroup_v2"
        else scope_name
    )
    # Phase 6: leader PID is not parsed from proc stdout — leave 0.
    # Phase 7 will refresh this from the persisted record / cgroup.procs.
    _ = proc  # captured for forward use

    return Sensor(
        agent_key=descriptor.key,
        scope_path=scope_path,
        pid=0,
        mode=mode,
        caps=caps,
        oom_policy=oom_policy,
        persistent=persistent,
        installed_at=datetime.now(),
        systemd_unit_path=None,
    )


def list_sensors() -> tuple[Sensor, ...]:
    """List active ``azrael-*.scope`` units via ``systemctl --user``.

    Returns an empty tuple if ``systemctl`` is missing. Each match
    becomes a `Sensor` with a default ``Caps()`` and the current
    ``datetime.now()`` — the real install time comes from the
    persistence layer in Phase 7.
    """
    try:
        proc = subprocess.run(
            [
                "systemctl",
                "--user",
                "list-units",
                "--type=scope",
                "--no-legend",
                "--plain",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ()
    except subprocess.CalledProcessError:
        return ()

    out: list[Sensor] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith(_AZRAEL_PREFIX):
            continue
        # Format: "azrael-<key>-<leader>.scope  loaded  running  <pid>  ..."
        unit = line.split()[0]
        if not unit.endswith(".scope"):
            continue
        # Strip ".scope" then strip "-<digits>" to recover the agent key.
        bare = unit[: -len(".scope")]
        # The unit suffix is "-<leader_pid>"; peel the trailing digits.
        last_dash = bare.rfind("-")
        if last_dash <= 0:
            continue
        suffix = bare[last_dash + 1 :]
        if not suffix.isdigit():
            continue
        key = bare[:last_dash]
        if not key.startswith(_AZRAEL_PREFIX):
            continue
        agent_key = key[len(_AZRAEL_PREFIX) :]
        scope_path = f"/sys/fs/cgroup/user.slice/{unit}"
        out.append(
            Sensor(
                agent_key=agent_key,
                scope_path=scope_path,
                pid=0,
                mode="control",
                caps=Caps(),
                oom_policy="continue",
                persistent=False,
                installed_at=datetime.now(),
                systemd_unit_path=None,
            )
        )
    return tuple(out)


def remove_sensor(scope_path: str) -> None:
    """Phase 6: stub. Phase 7 will implement this."""
    raise NotImplementedError("Phase 7")


def set_sensor_caps(sensor: Sensor, caps: Caps) -> None:
    """Phase 6: stub. Phase 7 will implement this."""
    raise NotImplementedError("Phase 7")


__all__ = [
    "Sensor",
    "install_sensor",
    "list_sensors",
    "remove_sensor",
    "set_sensor_caps",
]
