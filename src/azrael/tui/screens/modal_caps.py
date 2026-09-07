"""Caps modal — edit cpu.weight / memory.max / memory.high on a scope.

Parses user input via `control.caps.parse_cpu_weight` / `parse_memory` and
applies the result via `control.applier.apply_caps`.
"""

from __future__ import annotations

from typing import ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from azrael.agents.descriptor import Caps
from azrael.control import applier
from azrael.control import caps as cap_parsers
from azrael.platforms._common import Scope
from azrael.platforms.backend import ResourceBackend


class CapsModal(ModalScreen[str]):
    """Three-field caps editor for a scope.

    On Enter, parses the three fields and dispatches via
    `control.applier.apply_caps`. The backend writes through `actions`
    so capabilities and OS errors are reported as `ActionResult`s
    instead of raising.
    """

    DEFAULT_CSS = """
    CapsModal {
        align: center middle;
    }
    CapsModal > Vertical {
        width: 70;
        height: 17;
        border: solid $wire;
        padding: 1;
        background: $bezel;
    }
    CapsModal Label {
        height: 1;
        color: $tick;
    }
    CapsModal Input {
        height: 3;
    }
    CapsModal #result {
        height: 3;
        padding: 1 0 0 0;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "dismiss_modal", "Cancel"),
        ("enter", "submit", "Apply"),
    ]

    def __init__(
        self,
        backend: ResourceBackend,
        scope: Scope,
        current_caps: Caps | None = None,
    ) -> None:
        super().__init__()
        self._backend = backend
        self._scope = scope
        self._current_caps = current_caps or Caps()

    def compose(self):  # type: ignore[no-untyped-def]
        with Vertical():
            yield Label(f"Edit caps for scope {self._scope.path}")
            yield Label("cpu.weight (1..10000) — leave blank to skip:")
            yield Input(
                value=str(self._current_caps.cpu_weight)
                if self._current_caps.cpu_weight is not None
                else "",
                id="cpu_input",
            )
            yield Label("memory.max (e.g. 4G, 'unlimited') — leave blank to skip:")
            yield Input(id="max_input")
            yield Label("memory.high (e.g. 6G, 'unlimited') — leave blank to skip:")
            yield Input(id="high_input")
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one("#cpu_input", Input).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss("")

    def action_submit(self) -> None:
        cpu_text = self.query_one("#cpu_input", Input).value.strip()
        max_text = self.query_one("#max_input", Input).value.strip()
        high_text = self.query_one("#high_input", Input).value.strip()
        result = self.query_one("#result", Static)

        parsed_cpu: int | None = None
        parsed_max: int | None = None
        parsed_high: int | None = None
        try:
            if cpu_text:
                parsed_cpu = cap_parsers.parse_cpu_weight(cpu_text)
            if max_text:
                parsed_max = cap_parsers.parse_memory(max_text)
            if high_text:
                parsed_high = cap_parsers.parse_memory(high_text)
        except ValueError as exc:
            result.update(f"[red]invalid: {exc}[/red]")
            return

        if parsed_cpu is None and parsed_max is None and parsed_high is None:
            result.update(
                "[red]at least one of cpu.weight / memory.max / memory.high required[/red]"
            )
            return

        caps = Caps(cpu_weight=parsed_cpu, memory_max=parsed_max, memory_high=parsed_high)
        results = applier.apply_caps(self._backend, self._scope, caps)
        if not results:
            result.update("[yellow]nothing applied[/yellow]")
            return
        lines: list[str] = []
        ok = True
        for r in results:
            if r.ok:
                lines.append(f"[green]OK[/green] {r.message}")
            else:
                ok = False
                lines.append(f"[red]ERR[/red] {r.error}")
        result.update("\n".join(lines))
        if ok:
            self.dismiss("\n".join(r.message for r in results if r.ok))

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key == "escape":
            self.dismiss("")


__all__ = ["CapsModal"]
