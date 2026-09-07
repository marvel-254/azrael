from __future__ import annotations

from typing import TYPE_CHECKING

from azrael.platforms.backend import ResourceBackend

if TYPE_CHECKING:
    from azrael.agents.descriptor import AgentDescriptor


def scan_loose(backend: ResourceBackend) -> dict[int, AgentDescriptor]:
    return backend.discover_loose()


__all__ = ["scan_loose"]
