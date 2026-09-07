"""ProcessTable — sortable table of processes for the focused agent.

Per PLAN §9 + §16 anti-pattern #9, the I/O columns are labelled
`I/O throughput` (not "disk I/O"). The backend exposes page-cache
rchar/wchar; that disclosure comment lives here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar, Literal

from textual.widgets import DataTable

from azrael.platforms._common import ProcessMetrics
from azrael.tui.theme import GLOBAL

SortKey = Literal["cpu", "mem", "pid", "name", "io"]


def _fmt_bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "K", "M", "G", "T"):
        if f < 1024 or unit == "T":
            if unit == "B":
                return f"{int(f)}"
            return f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}T"


def _fmt_rate(bps: float) -> str:
    return _fmt_bytes(int(bps)) + "/s"


def _heat(pct: float) -> str:
    if pct >= 90:
        return GLOBAL.needle_crit
    if pct >= 70:
        return GLOBAL.needle_warn
    return GLOBAL.readout


class ProcessTable(DataTable[Any]):
    """A DataTable of process metrics for the currently-focused agent."""

    DEFAULT_CSS = """
    ProcessTable {
        height: 1fr;
        border: solid $wire;
    }
    """

    _COLUMNS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("pid", "PID"),
        ("cpu_pct", "CPU%"),
        ("mem_rss", "MEM"),
        ("nice", "NI"),
        ("io_rd_rate", "R/s"),
        ("io_wr_rate", "W/s"),
        ("state", "STATE"),
        ("cmd", "COMMAND"),
    )

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id, zebra_stripes=True, cursor_type="row")
        for key, label in self._COLUMNS:
            self.add_column(label, key=key)
        self._sort_key: SortKey = "cpu"

    def set_sort(self, key: SortKey) -> None:
        self._sort_key = key
        self.refresh()

    def set_processes(
        self, processes: tuple[ProcessMetrics, ...] | Iterable[ProcessMetrics]
    ) -> None:
        self.clear()
        procs = tuple(processes)
        if not procs:
            return

        def sort_key(p: ProcessMetrics) -> float | int | str:
            if self._sort_key == "cpu":
                return p.cpu_pct
            if self._sort_key == "mem":
                return p.mem_rss
            if self._sort_key == "pid":
                return p.pid
            if self._sort_key == "name":
                return p.cmd
            if self._sort_key == "io":
                return p.io_rd_rate + p.io_wr_rate
            return p.cpu_pct

        sorted_procs = sorted(procs, key=sort_key, reverse=self._sort_key in ("cpu", "mem", "io"))

        for p in sorted_procs:
            cpu_color = _heat(p.cpu_pct)
            pid_str = f"{p.pid}"
            cpu_str = f"{p.cpu_pct:5.1f}%"
            self.add_row(
                pid_str,
                f"[{cpu_color}]{cpu_str}[/]",
                _fmt_bytes(p.mem_rss),
                f"{p.nice}",
                _fmt_rate(p.io_rd_rate),
                _fmt_rate(p.io_wr_rate),
                p.state,
                p.cmd,
                key=str(p.pid),
            )

    def get_selected_pid(self) -> int:
        try:
            row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
            if row_key is None or row_key.value is None:
                return 0
            return int(row_key.value)
        except (AttributeError, IndexError, KeyError, ValueError):
            return 0


__all__ = ["ProcessTable", "SortKey"]
