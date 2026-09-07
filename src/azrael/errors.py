"""Scan agent log directories for recent error lines and summarize counts."""
from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ErrorReport:
    agent_key: str
    total_errors: int
    sample_lines: tuple[str, ...]


def scan(log_dirs: Iterable[Path], *, max_lines_per_file: int = 2000) -> dict[str, ErrorReport]:
    """Walk each log dir, count lines containing 'error' or 'fail' (case-insensitive).

    Returns a mapping of agent_key -> ErrorReport. Empty mapping if nothing found.
    """
    raise NotImplementedError
