from __future__ import annotations

from azrael.agents.builtin import builtin_descriptors


def test_builtin_returns_nine_agents() -> None:
    assert len(builtin_descriptors) == 9


def test_builtin_keys_are_unique() -> None:
    keys = [d.key for d in builtin_descriptors]
    assert len(keys) == len(set(keys))


def test_builtin_all_have_sensor_template() -> None:
    for d in builtin_descriptors:
        assert d.sensor_template is not None
        assert "{key}" in d.sensor_template
        assert "{cmd}" in d.sensor_template


def test_builtin_known_agents_present() -> None:
    expected = {
        "opencode",
        "hermes",
        "kilo-code",
        "openclaw",
        "goose",
        "claude-code",
        "openclaude",
        "cline",
        "freebuff",
    }
    keys = {d.key for d in builtin_descriptors}
    assert expected <= keys


def test_builtin_all_have_scope_fragments_with_dot_scope() -> None:
    for d in builtin_descriptors:
        assert ".scope" in d.scope_fragments


def test_builtin_display_names_have_no_uppercase_eyebrow() -> None:
    # design rule: display names are sentence-cased, not ALL CAPS
    for d in builtin_descriptors:
        assert d.display_name == d.display_name.strip()
        assert d.display_name.upper() != d.display_name or len(d.display_name) <= 3
