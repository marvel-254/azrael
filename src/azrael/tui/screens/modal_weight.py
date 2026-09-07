"""Weight modal — set cpu.weight on the focused scope via `control.actions`."""

from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from azrael.control import actions as control_actions
from azrael.platforms._common import Scope
from azrael.platforms.backend import ResourceBackend


class WeightModal(ModalScreen[str]):
    """Prompt for a cpu.weight (1..10000) and apply via `control.actions.set_cpu_weight`."""

    DEFAULT_CSS = """
    WeightModal {
        align: center middle;
    }
    WeightModal > Vertical {
        width: 60;
        height: 11;
        border: solid $wire;
        padding: 1;
        background: $bezel;
    }
    WeightModal Label {
        height: 1;
        color: $tick;
    }
    WeightModal Input {
        height: 3;
    }
    WeightModal #result {
        height: 3;
        padding: 1 0 0 0;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "dismiss_modal", "Cancel"),
        ("enter", "submit", "Apply"),
    ]

    def __init__(self, backend: ResourceBackend, scope: Scope, current_weight: int = 100) -> None:
        super().__init__()
        self._backend = backend
        self._scope = scope
        self._current_weight = current_weight

    def compose(self):  # type: ignore[no-untyped-def]
        with Vertical():
            yield Label(f"Set cpu.weight on scope {self._scope.path}")
            yield Label("New cpu.weight (1..10000):")
            yield Input(value=str(self._current_weight), id="weight_input")
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one("#weight_input", Input).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss("")

    def action_submit(self) -> None:
        text = self.query_one("#weight_input", Input).value.strip()
        result = self.query_one("#result", Static)
        try:
            weight = int(text)
            if not 1 <= weight <= 10000:
                raise ValueError(f"cpu.weight must be 1..10000, got {weight}")
        except ValueError as exc:
            result.update(f"[red]invalid: {exc}[/red]")
            return
        action_result = control_actions.set_cpu_weight(self._backend, self._scope, weight)
        if action_result.ok:
            result.update(f"[green]{action_result.message}[/green]")
            self.dismiss(action_result.message)
        else:
            result.update(f"[red]{action_result.error}[/red]")

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key == "escape":
            self.dismiss("")


__all__ = ["WeightModal"]
