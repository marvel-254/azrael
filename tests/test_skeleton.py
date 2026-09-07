"""Phase 0: ensure the public stubs are importable and self-describing."""
from __future__ import annotations
import pytest
from azrael import errors, config


def test_errors_module_imports() -> None:
    assert hasattr(errors, "ErrorReport")
    assert hasattr(errors, "scan")
    assert callable(errors.scan)


def test_config_module_imports() -> None:
    assert hasattr(config, "Config")
    assert hasattr(config, "load")
    assert hasattr(config, "save")
    assert callable(config.load)
    assert callable(config.save)


def test_config_default_values() -> None:
    c = config.Config()
    assert c.refresh_interval_s == 1.0
    assert c.units == "binary"
    assert c.theme == "garage"


def test_errors_stub_raises() -> None:
    with pytest.raises(NotImplementedError):
        errors.scan([])
