"""Tests for the azrael CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from azrael.cli.main import main


def test_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    out = result.output
    for sub in ("tui", "gui", "list-agents", "watch", "cap", "kill", "install-sensor"):
        assert sub in out


def test_main_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_main_list_agents() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["list-agents"])
    assert result.exit_code == 0, result.output
    out = result.output
    for key in ("opencode", "hermes", "goose"):
        assert key in out


def test_main_gui_not_implemented() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["gui"])
    assert result.exit_code != 0
    assert "Phase 8" in result.output or "not implemented" in result.output.lower()


def test_main_install_sensor_prints_template() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["install-sensor", "--agent", "opencode", "--cmd", "opencode run"])
    assert result.exit_code == 0
    assert "systemd-run" in result.output
