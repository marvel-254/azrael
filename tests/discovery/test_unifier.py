from __future__ import annotations

from azrael.agents.descriptor import AgentDescriptor, Caps
from azrael.discovery.unifier import unify
from azrael.metrics.types import Agent, Sample
from azrael.platforms._common import Scope


def _agent(key: str) -> Agent:
    return Agent(
        key=key,
        descriptor_key=key,
        scope=Scope("fake", f"/fake/{key}-1.scope", None),
        processes=(),
        sample=Sample(
            timestamp=0.0, cpu_pct=0.0, mem_used=0, mem_max=None, throttle_pct=0.0, oom_kills=0
        ),
        caps=Caps(),
    )


def test_unifier_passes_scope_agents_unchanged_in_phase4() -> None:
    a = _agent("opencode")
    b = _agent("hermes")
    out = unify([a, b], loose_pids={}, backend=None)  # type: ignore[arg-type]
    assert out == (a, b)


def test_unifier_empty_inputs_returns_empty() -> None:
    out = unify([], loose_pids={}, backend=None)  # type: ignore[arg-type]
    assert out == ()


def test_unifier_accepts_loose_pid_descriptor() -> None:
    """Loose wiring is TODO; ensure the call accepts the loose shape."""
    descriptor = AgentDescriptor(
        key="claude-code",
        display_name="Claude Code",
        cmdline_needles=("claude",),
        scope_fragments=("claude", ".scope"),
    )
    out = unify([], loose_pids={1234: descriptor}, backend=None)  # type: ignore[arg-type]
    assert out == ()  # no scope agents; loose is still a stub


def test_unifier_returns_tuple_type() -> None:
    out = unify([_agent("x")], loose_pids={}, backend=None)  # type: ignore[arg-type]
    assert isinstance(out, tuple)
