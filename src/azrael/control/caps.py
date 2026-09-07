"""Parse CLI cap arguments into a `Caps` dataclass.

Pure functions; no I/O. Replaces the prototype's inline `fmt_bytes` /
`fmt` calls so the TUI and CLI agree on humanization.
"""

from __future__ import annotations

from typing import Final, Literal, cast

from azrael.agents.descriptor import Caps

_OOM_POLICIES: Final[frozenset[str]] = frozenset({"kill", "stop", "continue"})

_UNLIMITED_SENTINEL: Final[int] = -1


def parse_cpu_weight(s: str) -> int:
    """Parse a cpu.weight string (1..10000).

    Accepts an integer in decimal. Raises `ValueError` on empty,
    non-integer, out-of-range, or trailing-junk input.
    """
    text = s.strip()
    if not text:
        raise ValueError(f"cpu.weight must be 1..10000, got {s!r}")
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"cpu.weight must be an integer, got {s!r}") from exc
    if not 1 <= value <= 10000:
        raise ValueError(f"cpu.weight must be 1..10000, got {value}")
    return value


def parse_memory(s: str) -> int:
    """Parse a memory size string.

    Accepts a decimal integer with an optional suffix:
    ``K`` (1024), ``M`` (1024**2), ``G`` (1024**3), ``T`` (1024**4).
    ``B`` is accepted as an explicit-byte suffix. ``"0"`` returns 0.

    The literal strings ``"unlimited"``, ``"max"``, and ``"inf"``
    return ``-1`` — the internal "unlimited" sentinel the actions
    layer translates into the cgroup v2 ``"max\n"`` string.

    Raises `ValueError` on anything else.
    """
    text = s.strip().lower()
    if not text:
        raise ValueError(f"memory value must be non-empty, got {s!r}")
    if text in {"unlimited", "max", "inf"}:
        return _UNLIMITED_SENTINEL

    # Split numeric prefix from optional suffix.
    digits_end = 0
    while digits_end < len(text) and (text[digits_end].isdigit() or text[digits_end] == "."):
        digits_end += 1
    if digits_end == 0:
        raise ValueError(f"memory value must start with a number, got {s!r}")
    num_part = text[:digits_end]
    suffix = text[digits_end:].strip()

    try:
        value = int(num_part)
    except ValueError as exc:
        raise ValueError(f"memory value must be an integer, got {s!r}") from exc
    if value < 0:
        raise ValueError(f"memory value must be >= 0, got {value}")

    multipliers = {
        "": 1,
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "kib": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "mib": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
        "gib": 1024**3,
        "t": 1024**4,
        "tb": 1024**4,
        "tib": 1024**4,
    }
    if suffix not in multipliers:
        raise ValueError(f"unknown memory suffix {suffix!r} in {s!r}")
    return value * multipliers[suffix]


def parse_nice(s: str) -> int:
    """Parse a nice value (-20..19). Raises `ValueError` on bad input."""
    text = s.strip()
    if not text:
        raise ValueError(f"nice must be -20..19, got {s!r}")
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"nice must be an integer, got {s!r}") from exc
    if not -20 <= value <= 19:
        raise ValueError(f"nice must be -20..19, got {value}")
    return value


def format_bytes(b: int | None) -> str:
    """Humanize a byte count using binary units.

    Renders ``0`` as ``"0B"``, scales upward through K/M/G/T, and
    returns ``"unlimited"`` for the ``-1`` sentinel and ``None``.
    """
    if b is None or b == _UNLIMITED_SENTINEL or b < 0:
        return "unlimited"
    if b < 1024:
        return f"{b}B"
    units: tuple[tuple[str, int], ...] = (
        ("K", 1024),
        ("M", 1024**2),
        ("G", 1024**3),
        ("T", 1024**4),
    )
    chosen_unit = "K"
    chosen_divisor = 1024
    for unit, divisor in units:
        if b >= divisor:
            chosen_unit = unit
            chosen_divisor = divisor
    value = b / chosen_divisor
    return f"{value:.1f}{chosen_unit}"


def format_cpu_weight(w: int | None) -> str:
    """Format a cpu.weight for display."""
    if w is None:
        return "unset"
    return f"{w} (default 100)"


def caps_from_kwargs(
    *,
    cpu_weight: str | None = None,
    memory_max: str | None = None,
    memory_high: str | None = None,
    nice: str | None = None,
    oom_policy: str | None = None,
) -> Caps:
    """Build a `Caps` from CLI string kwargs.

    Each kwarg is parsed via its helper. ``None`` means "leave the
    field unset on the resulting `Caps`" — ``caps_from_kwargs()``
    returns the all-``None`` default. Raises `ValueError` on bad
    input (the parser does, this just propagates).
    """
    parsed_cpu = parse_cpu_weight(cpu_weight) if cpu_weight is not None else None
    parsed_max = parse_memory(memory_max) if memory_max is not None else None
    parsed_high = parse_memory(memory_high) if memory_high is not None else None
    parsed_nice = parse_nice(nice) if nice is not None else None
    parsed_oom: str | None = None
    if oom_policy is not None:
        if oom_policy not in _OOM_POLICIES:
            raise ValueError(
                f"oom_policy must be one of {sorted(_OOM_POLICIES)}, got {oom_policy!r}"
            )
        parsed_oom = oom_policy
    # mypy: parsed_oom is narrowed to the literal union by the membership check.
    oom_literal: Literal["kill", "stop", "continue"] | None = (
        cast(Literal["kill", "stop", "continue"], parsed_oom) if parsed_oom is not None else None
    )

    return Caps(
        cpu_weight=parsed_cpu,
        memory_max=parsed_max,
        memory_high=parsed_high,
        nice=parsed_nice,
        oom_policy=oom_literal,
    )


__all__ = [
    "caps_from_kwargs",
    "format_bytes",
    "format_cpu_weight",
    "parse_cpu_weight",
    "parse_memory",
    "parse_nice",
]
