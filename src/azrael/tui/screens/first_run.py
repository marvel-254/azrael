"""First-run screen.

A simple screen shown by the App on `on_mount`. The App pops it as soon
as the first `sampler.tick()` returns data.
"""

from __future__ import annotations

from textual.screen import Screen
from textual.widgets import Static


class FirstRunScreen(Screen[None]):
    DEFAULT_CSS = """
    FirstRunScreen {
        align: center middle;
        background: $bg;
    }
    FirstRunScreen > Static {
        width: 60;
        height: 3;
        padding: 1;
    }
    """

    def compose(self):  # type: ignore[no-untyped-def]
        yield Static("azrael — first run. Detecting agents. Press q to quit.")


__all__ = ["FirstRunScreen"]
