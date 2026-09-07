"""Keybind reference footer.

Per PLAN Appendix B. Shows the active keybinds in a single `Static`.
`set_context("normal")` and `set_context("modal")` switch the displayed
keybinds (modals show only dismiss + confirm bindings).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from azrael.tui.theme import GLOBAL

if TYPE_CHECKING:
    from rich.visual import Visual


_NORMAL_KEYBINDS: tuple[tuple[str, str], ...] = (
    ("q", "quit"),
    ("r", "refresh"),
    ("← →", "switch agent"),
    ("↑ ↓", "row select"),
    ("c m p n i", "sort cpu/mem/pid/name/io"),
    ("k", "kill pid (SIGTERM)"),
    ("K", "stop scope"),
    ("N", "renice"),
    ("W", "weight"),
    ("C", "caps"),
    ("u", "toggle units"),
    ("?", "help"),
    ("^L", "redraw"),
)

_MODAL_KEYBINDS: tuple[tuple[str, str], ...] = (
    ("esc", "dismiss"),
    ("enter", "confirm"),
)


class KeybindFooter(Static):
    DEFAULT_CSS = """
    KeybindFooter {
        height: 1;
        width: 1fr;
        padding: 0 1;
        background: $bezel;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._ctx = "normal"
        self._theme = GLOBAL

    def set_context(self, ctx: str) -> None:
        self._ctx = ctx
        self.refresh()

    def render(self) -> Visual:
        from rich.text import Text

        return Text.from_markup(self._render_str())

    def _render_str(self) -> str:
        binds = _MODAL_KEYBINDS if self._ctx == "modal" else _NORMAL_KEYBINDS
        wire = self._theme.wire
        tick = self._theme.tick
        readout = self._theme.readout
        parts: list[str] = []
        for key, action in binds:
            parts.append(f"[{readout}]{key}[/] [{wire}]│[/] [{tick}]{action}[/]")
        return " ".join(parts)


__all__ = ["KeybindFooter"]
