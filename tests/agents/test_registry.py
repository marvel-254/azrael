from __future__ import annotations

import pytest

from azrael.agents.descriptor import AgentDescriptor
from azrael.agents.registry import Registry


def _desc(
    key: str,
    display: str,
    needles: tuple[str, ...] = (),
    fragments: tuple[str, ...] = (),
) -> AgentDescriptor:
    return AgentDescriptor(
        key=key,
        display_name=display,
        cmdline_needles=needles,
        scope_fragments=fragments,
    )


def test_registry_get_known_key() -> None:
    d = _desc("opencode", "OpenCode", needles=("opencode",), fragments=("opencode",))
    r = Registry([d])
    assert r.get("opencode") is d


def test_registry_get_unknown_key_returns_none() -> None:
    r = Registry([_desc("opencode", "OpenCode", needles=("opencode",), fragments=("opencode",))])
    assert r.get("missing") is None


def test_registry_match_scope_longest_fragment_wins() -> None:
    short = _desc("oc", "Short", fragments=("opencode",))
    long = _desc("oc-test", "Long", fragments=("opencode-test",))
    r = Registry([short, long])
    # scope name containing the longer fragment should match the long descriptor
    assert r.match_scope("opencode-test.scope") is long
    assert r.match_scope("opencode.scope") is short


def test_registry_match_cmdline_case_insensitive() -> None:
    d = _desc("opencode", "OpenCode", needles=("opencode",), fragments=("opencode",))
    r = Registry([d])
    assert r.match_cmdline("OpenCode CLI --help") is d
    assert r.match_cmdline("/usr/bin/opencode run") is d
    assert r.match_cmdline("hermes foo") is None


def test_registry_match_scope_no_match_returns_none() -> None:
    r = Registry([_desc("opencode", "OpenCode", fragments=("opencode",))])
    assert r.match_scope("hermes-1234.scope") is None


def test_registry_match_cmdline_no_match_returns_none() -> None:
    r = Registry([_desc("opencode", "OpenCode", needles=("opencode",))])
    assert r.match_cmdline("hermes foo") is None


def test_registry_all_returns_tuple_sorted_by_display_name() -> None:
    d1 = _desc("a", "Zebra", needles=("a",), fragments=("a",))
    d2 = _desc("b", "Apple", needles=("b",), fragments=("b",))
    d3 = _desc("c", "Mango", needles=("c",), fragments=("c",))
    r = Registry([d1, d2, d3])
    names = tuple(d.display_name for d in r.all())
    assert names == ("Apple", "Mango", "Zebra")


def test_registry_duplicate_key_raises() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        Registry(
            [
                _desc("x", "X1", needles=("x",), fragments=("x",)),
                _desc("x", "X2", needles=("x",), fragments=("x",)),
            ]
        )


def test_registry_discover_includes_builtins(tmp_path) -> None:
    r = Registry.discover(user_dir=tmp_path)
    assert len(r.all()) >= 9
