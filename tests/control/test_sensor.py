"""Tests for `azrael.control.sensor` — install / list / remove / set_caps."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from azrael.agents.descriptor import AgentDescriptor, Caps
from azrael.control.sensor import (
    Sensor,
    install_sensor,
    list_sensors,
    remove_sensor,
    set_sensor_caps,
)
from azrael.platforms._common import CAP_SENSOR, Capabilities


@dataclass
class FakeBackend:
    name: str = "linux_cgroup_v2"
    capabilities: Capabilities = field(default_factory=lambda: frozenset({CAP_SENSOR}))


_DESCRIPTOR = AgentDescriptor(
    key="opencode",
    display_name="OpenCode",
    cmdline_needles=("opencode",),
    scope_fragments=("opencode-",),
)


class TestInstallSensor:
    def test_install_sensor_runs_systemd_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

        def fake_run(argv: list[str], **kwargs: Any) -> Any:
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return fake_proc

        monkeypatch.setattr(subprocess, "run", fake_run)
        s = install_sensor(
            FakeBackend(),
            _DESCRIPTOR,
            ["opencode", "run"],
            caps=Caps(cpu_weight=200),
        )
        argv = captured["argv"]
        assert "--unit=azrael-opencode" in argv
        assert "--property=CPUWeight=200" in argv
        assert argv[-2:] == ["opencode", "run"]
        assert captured["kwargs"].get("check") is True
        assert captured["kwargs"].get("capture_output") is True
        assert isinstance(s, Sensor)
        assert s.agent_key == "opencode"

    def test_install_sensor_includes_memory_max_property(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda argv, **kw: captured.setdefault("argv", argv) or fake_proc,
        )
        install_sensor(
            FakeBackend(),
            _DESCRIPTOR,
            ["opencode"],
            caps=Caps(memory_max=4 * 1024**3),
        )
        assert any(a.startswith("--property=MemoryMax=") for a in captured["argv"])

    def test_install_sensor_no_caps_omits_properties(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda argv, **kw: captured.setdefault("argv", argv) or fake_proc,
        )
        install_sensor(FakeBackend(), _DESCRIPTOR, ["opencode"])
        assert not any(a.startswith("--property=") for a in captured["argv"])

    def test_install_sensor_oom_policy_continue_omits_property(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda argv, **kw: captured.setdefault("argv", argv) or fake_proc,
        )
        install_sensor(
            FakeBackend(),
            _DESCRIPTOR,
            ["opencode"],
            oom_policy="continue",
        )
        assert not any("MemoryOOMPolicy" in a for a in captured["argv"])

    def test_install_sensor_oom_policy_kill_adds_property(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda argv, **kw: captured.setdefault("argv", argv) or fake_proc,
        )
        install_sensor(FakeBackend(), _DESCRIPTOR, ["opencode"], oom_policy="kill")
        assert any(a == "--property=MemoryOOMPolicy=kill" for a in captured["argv"])

    def test_install_sensor_raises_when_backend_lacks_cap_sensor(self) -> None:
        b = FakeBackend(capabilities=frozenset())
        with pytest.raises(RuntimeError):
            install_sensor(b, _DESCRIPTOR, ["opencode"])

    def test_install_sensor_raises_when_systemctl_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(argv: list[str], **kwargs: Any) -> Any:
            raise FileNotFoundError(2, "No such file", "systemd-run")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(FileNotFoundError):
            install_sensor(FakeBackend(), _DESCRIPTOR, ["opencode"])

    def test_install_sensor_validates_inputs(self) -> None:
        with pytest.raises(ValueError):
            install_sensor(FakeBackend(), _DESCRIPTOR, [], mode="control")
        with pytest.raises(ValueError):
            install_sensor(FakeBackend(), _DESCRIPTOR, ["x"], mode="bad")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            install_sensor(FakeBackend(), _DESCRIPTOR, ["x"], oom_policy="bad")  # type: ignore[arg-type]


class TestListSensors:
    def test_list_sensors_filters_to_azrael_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stdout = (
            "azrael-opencode-1234.scope loaded running 1234 /sbin/opencode\n"
            "azrael-hermes-5678.scope loaded running 5678 /sbin/hermes\n"
            "foo.scope loaded running 9999 /usr/bin/foo\n"
        )
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_proc)

        sensors = list_sensors()
        keys = sorted(s.agent_key for s in sensors)
        assert keys == ["hermes", "opencode"]
        for s in sensors:
            assert isinstance(s, Sensor)

    def test_list_sensors_returns_empty_when_systemctl_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(argv: list[str], **kwargs: Any) -> Any:
            raise FileNotFoundError(2, "No such file", "systemctl")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert list_sensors() == ()

    def test_list_sensors_returns_empty_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(argv: list[str], **kwargs: Any) -> Any:
            raise subprocess.CalledProcessError(1, argv, output="", stderr="bad")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert list_sensors() == ()


class TestStubs:
    def test_remove_sensor_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            remove_sensor("/some/path.scope")

    def test_set_sensor_caps_raises_not_implemented(self) -> None:
        s = Sensor(
            agent_key="opencode",
            scope_path="/x",
            pid=0,
            mode="control",
            caps=Caps(),
            oom_policy="continue",
            persistent=False,
            installed_at=__import__("datetime").datetime.now(),
            systemd_unit_path=None,
        )
        with pytest.raises(NotImplementedError):
            set_sensor_caps(s, Caps())
