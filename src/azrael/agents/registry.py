from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from azrael.agents.builtin import builtin_descriptors
from azrael.agents.descriptor import AgentDescriptor
from azrael.agents.user import load_user_descriptors


class Registry:
    def __init__(self, descriptors: Iterable[AgentDescriptor]) -> None:
        by_key: dict[str, AgentDescriptor] = {}
        for d in descriptors:
            if d.key in by_key:
                raise ValueError(f"duplicate descriptor key: {d.key!r}")
            by_key[d.key] = d
        self._by_key = by_key

    def get(self, key: str) -> AgentDescriptor | None:
        return self._by_key.get(key)

    def match_scope(self, scope_name: str) -> AgentDescriptor | None:
        best: AgentDescriptor | None = None
        best_len = -1
        low = scope_name.lower()
        for d in self._by_key.values():
            for frag in d.scope_fragments:
                if frag in low and len(frag) > best_len:
                    best, best_len = d, len(frag)
        return best

    def match_cmdline(self, cmdline: str) -> AgentDescriptor | None:
        best: AgentDescriptor | None = None
        best_len = -1
        low = cmdline.lower()
        for d in self._by_key.values():
            for n in d.cmdline_needles:
                if n in low and len(n) > best_len:
                    best, best_len = d, len(n)
        return best

    def all(self) -> tuple[AgentDescriptor, ...]:
        return tuple(sorted(self._by_key.values(), key=lambda d: d.display_name))

    @classmethod
    def discover(cls, user_dir: Path | None = None) -> Registry:
        descs: list[AgentDescriptor] = list(builtin_descriptors)
        if user_dir is not None:
            descs.extend(load_user_descriptors(user_dir))
        return cls(descs)


__all__ = ["Registry"]
