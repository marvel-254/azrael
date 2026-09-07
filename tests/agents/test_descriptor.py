from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from azrael.agents.descriptor import AgentDescriptor, Caps


def test_descriptor_basic_construction() -> None:
    d = AgentDescriptor(
        key="opencode",
        display_name="OpenCode",
        cmdline_needles=("opencode",),
        scope_fragments=("opencode",),
    )
    assert d.key == "opencode"
    assert d.display_name == "OpenCode"
    assert d.cmdline_needles == ("opencode",)
    assert d.scope_fragments == ("opencode",)
    assert d.user_log_paths == ()
    assert d.config_path_hints == ()
    assert d.sensor_template is None
    assert d.website is None
    assert isinstance(d.default_caps, Caps)


def test_descriptor_is_frozen() -> None:
    d = AgentDescriptor(
        key="opencode",
        display_name="OpenCode",
        cmdline_needles=("opencode",),
        scope_fragments=("opencode",),
    )
    with pytest.raises(FrozenInstanceError):
        d.key = "other"  # type: ignore[misc]


def test_descriptor_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="key must be non-empty"):
        AgentDescriptor(
            key="",
            display_name="X",
            cmdline_needles=("x",),
            scope_fragments=("x",),
        )


def test_descriptor_rejects_uppercase_key() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        AgentDescriptor(
            key="OpenCode",
            display_name="OpenCode",
            cmdline_needles=("opencode",),
            scope_fragments=("opencode",),
        )


def test_descriptor_with_default_caps() -> None:
    caps = Caps()
    assert caps.cpu_weight is None
    assert caps.memory_max is None
    assert caps.memory_high is None
    assert caps.nice is None
    assert caps.oom_policy is None


def test_descriptor_paths_default_empty() -> None:
    d = AgentDescriptor(
        key="x",
        display_name="X",
        cmdline_needles=("x",),
        scope_fragments=("x",),
    )
    assert isinstance(d.user_log_paths, tuple)
    assert isinstance(d.config_path_hints, tuple)
    assert d.user_log_paths == ()
    # Path(...) is allowed but defaults are empty
    d2 = AgentDescriptor(
        key="x",
        display_name="X",
        cmdline_needles=("x",),
        scope_fragments=("x",),
        user_log_paths=(Path("/tmp/x"),),
        config_path_hints=(Path("/tmp/x"),),
    )
    assert d2.user_log_paths == (Path("/tmp/x"),)
