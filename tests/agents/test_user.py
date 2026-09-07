from __future__ import annotations

import logging
from pathlib import Path

import pytest

from azrael.agents.user import load_user_descriptors


def test_load_user_descriptors_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert load_user_descriptors(tmp_path / "nope") == ()


def test_load_user_descriptors_parses_valid_toml(tmp_path: Path) -> None:
    toml = tmp_path / "myagent.toml"
    toml.write_text(
        'key = "myagent"\n'
        'display_name = "My Agent"\n'
        'cmdline_needles = ["myagent"]\n'
        'scope_fragments = ["myagent", ".scope"]\n'
        'website = "https://example.com"\n'
        'sensor_template = "systemd-run --user --scope {cmd}"\n'
    )
    out = load_user_descriptors(tmp_path)
    assert len(out) == 1
    d = out[0]
    assert d.key == "myagent"
    assert d.display_name == "My Agent"
    assert d.cmdline_needles == ("myagent",)
    assert d.scope_fragments == ("myagent", ".scope")
    assert d.website == "https://example.com"
    assert d.sensor_template == "systemd-run --user --scope {cmd}"


def test_load_user_descriptors_skips_malformed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not = valid toml [")
    with caplog.at_level(logging.WARNING, logger="azrael.agents.user"):
        out = load_user_descriptors(tmp_path)
    assert out == ()
    assert any("bad.toml" in r.message for r in caplog.records)


def test_load_user_descriptors_expands_user_in_path(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    toml = tmp_path / "x.toml"
    toml.write_text(
        'key = "x"\n'
        'display_name = "X"\n'
        'cmdline_needles = ["x"]\n'
        'scope_fragments = ["x"]\n'
        'user_log_paths = ["~/logs/x.log"]\n'
        'config_path_hints = ["~/cfg/x.toml"]\n'
    )
    (out,) = load_user_descriptors(tmp_path)
    assert out.user_log_paths == (fake_home / "logs" / "x.log",)
    assert out.config_path_hints == (fake_home / "cfg" / "x.toml",)


def test_load_user_descriptors_skips_missing_required_fields(tmp_path: Path) -> None:
    toml = tmp_path / "x.toml"
    toml.write_text('display_name = "X"\n')  # missing key, needles, fragments
    assert load_user_descriptors(tmp_path) == ()
