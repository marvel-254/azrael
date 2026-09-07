from __future__ import annotations

from azrael.platforms._common import Scope
from azrael.platforms.backend import ResourceBackend


def walk_scopes(backend: ResourceBackend) -> list[Scope]:
    return backend.discover_scopes()


__all__ = ["walk_scopes"]
