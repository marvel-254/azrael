"""Renice modal — change a process's nice value via `control.actions.renice`."""

from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from azrael.control import actions as control_actions
from azrael.platforms.backend import ResourceBackend


class ReniceModal(ModalScreen[str]):
    """Prompt for a nice value (-20..19) and apply via `control.actions.renice`."""

    DEFAULT_CSS = """
    ReniceModal {
        align: center middle;
    }
    ReniceModal > Vertical {
        width: 60;
        height: 11;
        border: solid $wire;
        padding: 1;
        background: $bezel;
    }
    ReniceModal Label {
        height: 1;
        color: $tick;
    }
    ReniceModal Input {
        height: 3;
    }
    ReniceModal #result {
        height: 3;
        padding: 1 0 0 0;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "dismiss_modal", "Cancel"),
        ("enter", "submit", "Apply"),
    ]

    def __init__(self, backend: ResourceBackend, pid: int, current_nice: int = 0) -> None:
        super().__init__()
        self._backend = backend
        self._pid = pid
        self._current_nice = current_nice

    def compose(self):  # type: ignore[no-untyped-def]
        with Vertical():
            yield Label(f"Renice pid {self._pid} (current: {self._current_nice})")
            yield Label("New nice value (-20..19):")
            yield Input(value=str(self._current_nice), id="nice_input")
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one("#nice_input", Input).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss("")

    def action_submit(self) -> None:
        text = self.query_one("#nice_input", Input).value.strip()
        result = self.query_one("#result", Static)
        try:
            nice = int(text)
            if not -20 <= nice <= 19:
                raise ValueError(f"nice must be -20..19, got {nice}")
        except ValueError as exc:
            result.update(f"[red]invalid: {exc}[/red]")
            return
        action_result = control_actions.renice(self._backend, self._pid, nice)
        if action_result.ok:
            result.update(f"[green]{action_result.message}[/green]")
            self.dismiss(action_result.message)
        else:
            result.update(f"[red]{action_result.error}[/red]")

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key == "escape":
            self.dismiss("")


__all__ = ["ReniceModal"]
