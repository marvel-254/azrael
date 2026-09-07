from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Literal

from azrael.agents.descriptor import AgentDescriptor, Caps

_OomPolicy = Literal["kill", "stop", "continue"]

_log = logging.getLogger("azrael.agents.user")


def load_user_descriptors(user_dir: Path) -> tuple[AgentDescriptor, ...]:
    if not user_dir.is_dir():
        return ()
    out: list[AgentDescriptor] = []
    for path in sorted(user_dir.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as exc:
            _log.warning("skipping malformed user descriptor %s: %s", path, exc)
            continue
        try:
            out.append(_from_dict(data))
        except (KeyError, ValueError) as exc:
            _log.warning("skipping invalid user descriptor %s: %s", path, exc)
    return tuple(out)


def _from_dict(data: dict[str, object]) -> AgentDescriptor:
    key = str(data["key"])
    display_name = str(data["display_name"])
    needles = tuple(str(n) for n in _as_list(data.get("cmdline_needles")))
    fragments = tuple(str(f) for f in _as_list(data.get("scope_fragments")))
    if not needles and not fragments:
        raise ValueError("descriptor must declare at least one needle or fragment")
    user_log_paths = tuple(Path(str(p)).expanduser() for p in _as_list(data.get("user_log_paths")))
    config_path_hints = tuple(
        Path(str(p)).expanduser() for p in _as_list(data.get("config_path_hints"))
    )
    caps_raw = data.get("default_caps") or {}
    caps_dict = caps_raw if isinstance(caps_raw, dict) else {}
    caps = Caps(
        cpu_weight=_as_opt_int(caps_dict.get("cpu_weight")),
        memory_max=_as_opt_int(caps_dict.get("memory_max")),
        memory_high=_as_opt_int(caps_dict.get("memory_high")),
        nice=_as_opt_int(caps_dict.get("nice")),
        oom_policy=_as_oom(caps_dict.get("oom_policy")),
    )
    sensor_template = data.get("sensor_template")
    website = data.get("website")
    return AgentDescriptor(
        key=key,
        display_name=display_name,
        cmdline_needles=needles,
        scope_fragments=fragments,
        user_log_paths=user_log_paths,
        config_path_hints=config_path_hints,
        default_caps=caps,
        sensor_template=str(sensor_template) if sensor_template is not None else None,
        website=str(website) if website is not None else None,
    )


def _as_list(v: object) -> list[object]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def _as_opt_int(v: object) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    return int(str(v))


def _as_oom(v: object) -> _OomPolicy | None:
    if v is None:
        return None
    s = str(v)
    if s not in ("kill", "stop", "continue"):
        raise ValueError(f"invalid oom_policy {s!r}")
    return s  # type: ignore[return-value]


__all__ = ["load_user_descriptors"]
