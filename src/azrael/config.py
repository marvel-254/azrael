"""Load and save azrael configuration from ~/.config/azrael/config.toml."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    refresh_interval_s: float = 1.0
    units: str = "binary"  # "binary" | "si"
    default_agent_caps: dict[str, dict[str, object]] = field(default_factory=dict)
    sensors_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "azrael" / "sensors")
    theme: str = "garage"  # see PLAN §6.1


DEFAULT_PATH: Path = Path.home() / ".config" / "azrael" / "config.toml"


def load(path: Path = DEFAULT_PATH) -> Config:
    """Load config from `path`; return defaults if file is missing."""
    raise NotImplementedError


def save(config: Config, path: Path = DEFAULT_PATH) -> None:
    """Persist config to `path` (creates parent dirs)."""
    raise NotImplementedError
