"""Smoke test: the package imports and has a version."""
from __future__ import annotations
import azrael
from azrael.version import __version__


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert len(__version__.split(".")) == 3


def test_package_exports_version() -> None:
    assert azrael.__version__ == __version__
