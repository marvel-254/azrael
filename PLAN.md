# azrael — Architecture Plan

> A TUI + GUI monitor and resource controller for AI agent harnesses
> (opencode, hermes, kilo-code, openclaw, goose, claude code, openclaude,
> cline, freebuff, …).

The directory `/home/marvel/azrael/` keeps the misspelling (preserved as the
project root); the **product name** is `azrael` (the "angel of death" for
runaway processes — fitting for a tool that prevents them).

This plan graduates the working prototype (`oplm` + `oplm-qt`) into a
proper, extensible product. It is written to be enough to scaffold the
project without being a novel.

---

## 1. Goals & non-goals

### Goals

1. **Discover** running agent harnesses on the box — by cgroup scope
   first, by `/proc/<pid>/cmdline` fallback second.
2. **Measure** per-agent CPU%, RSS, cgroup memory.current/max, throttle
   time, OOM kills, process tree.
3. **Display** that data as a deliberately-designed *car dashboard* —
   not a generic SaaS tile grid.
4. **Control** per-agent resource caps: cgroup `cpu.weight`,
   `memory.max`/`memory.high`, and per-process `nice` (when cgroup is
   not available).
5. **Install sensors** — wrap unwrapped agents in a systemd `--user`
   scope so azrael can both monitor and control them.
6. **Work** identically across Linux (cgroup v2, primary), Windows (Job
   Objects, secondary), and macOS (best-effort, ulimit + sample only).

### Non-goals (this release)

- macOS is **monitor-only** by design — no per-process caps. Sandboxing
  primitives on Darwin are not equivalent to cgroup v2 and trying to
  fake them produces a worse tool.
- No cloud/remote-agent discovery. Local box only.
- No automatic killing of any process without an explicit user action
  (or a configured `oom_policy = kill` cap — see §7).
- No telemetry, no analytics, no network calls.

---

## 2. Supported agents — registry pattern

The prototype hard-codes `AGENTS = ("opencode", "openclaude", "hermes",
"goose", "freebuff")`. azrael replaces that with an **extensible
registry** discovered from TOML.

### Module: `azrael.agents`

```
azrael/
  agents/
    __init__.py
    registry.py     # Registry singleton + discovery entry points
    descriptor.py   # AgentDescriptor dataclass
    builtin.py      # Built-in descriptors shipped with azrael
    user.py         # Loader for ~/.config/azrael/agents/*.toml
```

### `AgentDescriptor` (dataclass)

```
@dataclass(frozen=True)
class AgentDescriptor:
    key: str                       # "opencode"
    display_name: str              # "OpenCode"
    cmdline_needles: tuple[str,…]  # substrings matched against /proc cmdline
    scope_fragments: tuple[str,…]  # substrings matched against cgroup scope name
    user_log_paths: tuple[Path,…]  # for error scan
    config_path_hints: tuple[Path,…]  # for first-run detection
    default_caps: Caps             # see §11
    sensor_template: str | None    # shell-style systemd-run --user --scope=… invocation
    website: str | None
```

### `Registry`

```
class Registry:
    def __init__(self, descriptors: Iterable[AgentDescriptor]) -> None: ...
    def get(self, key: str) -> AgentDescriptor | None: ...
    def match_scope(self, scope_name: str) -> AgentDescriptor | None: ...
    def match_cmdline(self, cmdline: str) -> AgentDescriptor | None: ...
    def all(self) -> list[AgentDescriptor]: ...
```

**Built-in descriptors** (`builtin.py`) cover: opencode, hermes,
kilo-code, openclaw, goose, claude-code, openclaude, cline, freebuff.
User can drop additional `~/.config/azrael/agents/<name>.toml` files
that get loaded by `Registry.discover()`.

The match is **first-wins**; ties resolve by `display_name` length
descending (longer = more specific).

---

## 3. Platform support matrix

| Feature                       | Linux (cgroup v2) | Windows (Job Objects) | macOS (ulimit + ps) |
|-------------------------------|-------------------|------------------------|----------------------|
| Discover scopes / containers  | ✅ systemd `--user` scope tree | ✅ Job Object list by PID ancestry | ⚠ best-effort by `pgrep` |
| CPU% per agent                | ✅ `cpu.stat` deltas | ✅ `GetProcessTimes` deltas | ⚠ `ps` deltas, lower fidelity |
| Memory current / max          | ✅ `memory.current`, `memory.max` | ✅ `ProcessMemoryCounters`, `JobObjectExtendedLimitInformation` | ⚠ `VmRSS` only |
| Throttle / OOM stats          | ✅ `cpu.stat.nr_throttled`, `memory.events.oom_kill` | ⚠ limited | ❌ n/a |
| **Cap** CPU weight            | ✅ `cpu.weight` (1..10000) | ❌ n/a | ❌ n/a |
| **Cap** memory                | ✅ `memory.max`, `memory.high` | ⚠ `JobObjectMemoryLimit` | ❌ n/a |
| **Cap** per-process nice      | ✅ `setpriority` | ⚠ `SetPriorityClass` | ⚠ `setpriority` |
| Install sensor                | ✅ `systemd-run --user --scope` | ❌ not in v1 | ❌ n/a |
| Kill scope / job              | ✅ `systemctl --user stop` | ✅ `TerminateJobObject` | ⚠ `kill -TERM` |

The seam is `azrael.platforms.ResourceBackend` (see §5).

---

## 4. Code layout

```
azrael/                            # the project root (kept misspelled)
  pyproject.toml
  README.md
  PLAN.md                          # this file
  AGENTS.md                        # contributor guide
  src/
    azrael/
      __init__.py
      version.py
      errors.py                    # agent-log error scan

      agents/
        __init__.py
        descriptor.py
        registry.py
        builtin.py
        user.py

      platforms/
        __init__.py
        backend.py                 # ResourceBackend Protocol + factory
        linux_cgroup_v2.py
        windows_jobobj.py
        darwin.py
        _common.py                 # shared types (CpuSample, MemSample, ...)

      discovery/
        __init__.py
        scope_walker.py            # walks user.slice / user@uid.service
        process_scanner.py         # walks /proc cmdline for loose agents
        unifier.py                 # merges scope + loose into Agent instances

      metrics/
        __init__.py
        sampler.py                 # top-level Sampler (orchestrator)
        cgroup_reader.py
        proc_reader.py
        types.py                   # Sample, Timeseries, Caps, ScopeMetrics

      control/
        __init__.py
        caps.py                    # parse --cpu 50%, --mem 4G, --weight N
        actions.py                 # kill_pid, kill_scope, set_weight, set_mem_max, renice
        sensor.py                  # install_sensor, list_sensors, remove_sensor

      history/
        __init__.py
        ring.py                    # in-memory rolling ring (per-agent)
        store.py                   # append-only text + optional sqlite

      tui/
        __init__.py
        app.py                     # Textual App
        screens/
          dashboard.py
          modal_caps.py
          modal_nice.py
          first_run.py
        widgets/
          gauge.py                 # text-mode analog gauge (Braille/Block)
          agent_strip.py
          process_table.py
          sparkline.py

      gui/
        __init__.py
        app.py                     # QApplication entry
        main_window.py
        widgets/
          analog_gauge.py          # real QPainter gauge (ported from prototype)
          agent_strip.py
          process_table.py
          chrome.py                # bezel / inner-glow effects

      cli/
        __init__.py
        main.py                    # argparse top-level
        cmd_tui.py
        cmd_gui.py
        cmd_watch.py
        cmd_cap.py
        cmd_install_sensor.py
        cmd_list_agents.py
        cmd_kill.py

      config.py                    # TOML loader for ~/.config/azrael/config.toml

  tests/
    unit/
      test_cgroup_parser.py        # text fixtures
      test_proc_stat_parser.py
      test_linux_backend.py        # mocked cgroup tree
      test_windows_backend.py      # mocked pywin32
      test_darwin_backend.py
      test_registry.py
      test_caps_parsing.py
      test_sensor_install.py       # mocked systemd-run
    fixtures/
      cgroup/
        user.slice/opencode-1234.scope/cpu.max
        ... (one fixture per file type)
      proc/
        1234/stat
        1234/status
        1234/cmdline
        1234/io
    tui/
      test_dashboard_render.py     # textual.run_test() snapshot test
    gui/
      test_gauge_paint.py          # QT_QPA_PLATFORM=offscreen

  docs/
    architecture.md                # rendered diagram of the seams
    onboarding.md
    screenshots/
```

---

## 5. Deep seams

These three modules are the deep modules — they hide the most
non-decision complexity behind a tiny interface.

### 5.1 `platforms.ResourceBackend` — the OS seam

**Why deep:** every other module needs to *do something* to a process
or a container. Concentrating all OS-specific logic here means the
rest of the codebase is portable by construction.

```
# azrael/platforms/backend.py
from typing import Protocol

class ResourceBackend(Protocol):
    name: str

    def discover_scopes(self) -> list[Scope]: ...
    def read_scope_metrics(self, scope: Scope) -> ScopeMetrics: ...
    def set_cpu_weight(self, scope: Scope, weight: int) -> None: ...
    def set_memory_max(self, scope: Scope, bytes: int) -> None: ...
    def set_memory_high(self, scope: Scope, bytes: int) -> None: ...
    def kill_scope(self, scope: Scope) -> None: ...
    def install_sensor(self, agent: AgentDescriptor, cmd: list[str]) -> Scope: ...
    def remove_sensor(self, scope: Scope) -> None: ...

    def discover_loose(self) -> dict[int, AgentDescriptor]: ...   # pid → agent
    def read_process_metrics(self, pid: int) -> ProcessMetrics: ...
    def kill_pid(self, pid: int, sig: int = 15) -> None: ...
    def renice(self, pid: int, nice: int) -> None: ...
```

`backend.detect() -> ResourceBackend` selects at runtime
(`/sys/fs/cgroup/user.slice` present → linux_cgroup_v2; `sys.platform`
else). macOS / Windows backends return a no-op `set_cpu_weight` /
`install_sensor` — capability flags on the Protocol make this explicit:

```
class ResourceBackend(Protocol):
    capabilities: Capabilities   # frozenset of {"cpu.weight", "memory.max", "sensor", ...}
```

### 5.2 `agents.Registry` — the identity seam

The UI / sampler all call `registry.match_scope(name)` /
`registry.match_cmdline(cmd)` — they never hardcode agent names.
Adding a new agent is one TOML file, no code change.

### 5.3 `metrics.Sampler` — the time seam

The Sampler is the only thing that calls `time.monotonic()` and
maintains per-agent rolling state. Everything else receives
**immutable `Sample` snapshots** with a monotonic timestamp. This is
what makes the TUI and GUI deterministically testable.

```
class Sampler:
    def __init__(self, backend: ResourceBackend, registry: Registry) -> None: ...
    def tick(self) -> World: ...           # one frame of truth
    def history(self, agent_key: str, window_s: float = 300) -> Timeseries: ...
```

`World` is the single value object passed to TUI / GUI / CLI:

```
@dataclass(frozen=True)
class World:
    agents: tuple[Agent, ...]           # one per scope or loose group
    system: SystemMetrics              # total cores, total RAM
    timestamp: float                   # monotonic
```

---

## 6. The "car dashboard" aesthetic

This is the most important design call in the project. The vision note
asks for a car dashboard; the easy thing is to ship another btop clone
or another SaaS card grid. We refuse both.

### 6.1 Design direction (opinionated, concrete)

- **Hero element**: 2–3 large analog gauges (round, ~220×220 in GUI,
  Braille-block rendered in TUI). One is the **system total** (RPM
  metaphor for whole-machine CPU%), one is the **focused agent**
  (torque / load metaphor), one is **memory as fuel** with the
  "tank" draining upward.
- **Chrome**: a dark, slightly warm "garage" background
  (`#1b1816` — *oxblood-tinged charcoal*, not pure `#000` and not the
  generic `#0f172a` Slate-900). The gauge rims use an inner-glow /
  inset shadow (`#000000` 0.6 alpha, 4px blur, 0/-2px offset) so
  they read as recessed instruments, not flat circles.
- **Typography** (GUI):
  - Labels — **Inter** (variable, 12px regular for tick labels, 14px
    medium for gauge titles). Inter is dense, optically tuned, and
    reads like a "spec sheet" face — fits gauges.
  - Numbers — **JetBrains Mono** (14px medium for tick numerals,
    28px bold for the center reading). Monospace keeps the needle
    "live" value from jittering left-right as digits change.
  - TUI mirrors this with **Iosevka Term** (or DejaVu Sans Mono
    fallback). No proportional fonts in the terminal.
- **Color palette** (named, exact):
  - `--bg`            `#1b1816`  garage charcoal
  - `--bezel`         `#2a2522`  instrument bezel
  - `--bezel-edge`    `#0e0c0b`  inner shadow
  - `--tick`            `#b9a892`  warm parchment for tick marks
  - `--needle`          `#e8c178`  amber (idle)
  - `--needle-warn`     `#e8893c`  orange (caution)
  - `--needle-crit`     `#c63a3a`  red (danger — only when actually critical)
  - `--readout`         `#f5ead2`  warm white for numbers
  - `--accent`          `#7fb88f`  muted green for "system OK"
  - `--wire`            `#3a322d`  thin lines / separators

### 6.2 Hard rules (enforced by code, not just taste)

1. **No rounded card-with-shadow kits.** Cards, if used, are square
   with 1px `--wire` border. No `border-radius: 12px; box-shadow`.
2. **No ALL-CAPS eyebrow labels.** Section titles are sentence-case
   Inter Medium, never `UPPERCASE TRACKED`.
3. **No decorative gradient washes.** The only gradients are
   *inside* the gauge (the warning arc) and the bezel inner-glow.
4. **No emoji as UI icons.** The needle, the tick, the center dot —
   these are the icons.
5. **The gauges are the hero.** Everything else is information
   density below them.
6. **Color means something.** `--needle-crit` only fires above 90%.
   `--accent` only when the value is in its safe range. Color is
   never used for decoration.

### 6.3 Gauge anatomy (GUI)

Each `AnalogGauge` paints, in order:

1. Bezel ring (gradient from `--bezel` to `--bezel-edge`, inner
   stroke 1px `--wire`).
2. Inner well (`--bg` filled circle, 4px smaller radius).
3. Outer tick ring (12 major ticks, 60 minor ticks, in `--tick`).
4. Numeric scale (0, 25, 50, 75, 100 in JetBrains Mono along the
   bottom arc).
5. Warning arc (90–100% drawn in `--needle-crit`, 8% alpha).
6. Needle (single 2px line from center, color from
   `idle/warn/crit` thresholds, with a 1px drop shadow).
7. Center hub (8px filled circle, `--bezel-edge`, with a 1px
   `--bezel-edge` outline).
8. Title (Inter Medium, top-left, inside the bezel).
9. Live readout (JetBrains Mono Bold 28px, top-right, format
   `{value:.0f}%` or `{used:.1f}G / {total:.1f}G` for memory).

The TUI version uses Unicode Braille (`⣀⣄⣤⣥⣆⣇⣏⣟⣯⣷⣿`) for
the arc fill and a `▲` for the needle — the prototype already does
it; the rebuild makes it composable.

---

## 7. Onboarding / first-run experience

`azrael` (no args) on a fresh install runs `cli.first_run`:

1. Detect platform → choose backend.
2. `Registry.discover()` → built-in + user descriptors.
3. For each known agent, try (in order):
   - **a)** Is there a cgroup scope matching it? → register as
     *wrapped* agent, no sensor needed.
   - **b)** Is the agent's binary on `PATH` and not currently
     running? → offer to install a sensor:
     `systemd-run --user --scope --unit=azrael-<key> <cmd>`
     Transient scope that wraps the next invocation. azrael writes
     the unit to `~/.local/share/azrael/sensors/` so it survives
     reboots if the user wants it persistent.
   - **c)** Is the agent already running *without* a sensor?
     → monitor as a loose process group; offer to renice it or to
     show the user the exact line to add to their agent wrapper:
     `exec systemd-run --user --scope --unit=azrael-<key> <agent-cmd>`
4. Show a one-screen **first-run dashboard** (TUI or GUI) that lists
   what was found, what was wrapped, and what was suggested.
5. Persist state in `~/.local/share/azrael/state.toml`.

The first-run screen writes `~/.config/azrael/config.toml` with
detected defaults the user can later edit.

### Sensor modes

- **monitor-only** — azrael wraps in a scope but never writes
  `cpu.weight` / `memory.max`; user opted out of control.
- **control** — azrael owns `cpu.weight` and `memory.max`; the user
  sees caps applied immediately.
- The default is **control**, with `oom_policy = kill` *off* by
  default (azrael never kills your agent automatically). Setting
  `oom_policy = kill` on a sensor means systemd itself kills the
  scope on OOM — azrael just shows the event.

---

## 8. The "sensor" concept, formalized

```
@dataclass(frozen=True)
class Sensor:
    agent_key: str
    scope_path: str             # Linux: /sys/fs/cgroup/.../<unit>.scope
    pid: int                    # leader PID
    mode: Literal["monitor-only", "control"]
    caps: Caps                  # current effective caps
    oom_policy: Literal["kill", "stop", "continue"]
    persistent: bool            # True = written to ~/.local/share/azrael/sensors/
    installed_at: datetime
    systemd_unit_path: Path | None
```

Operations (`azrael.control.sensor`):

- `install(agent: AgentDescriptor, cmd: list[str], mode, caps,
  persistent) -> Sensor`
- `remove(sensor: Sensor) -> None`
- `list_sensors() -> list[Sensor]`
- `set_caps(sensor: Sensor, caps: Caps) -> None`

The sensor file (`~/.local/share/azrael/sensors/<key>.scope.conf`)
is a small systemd unit fragment so the sensor can be re-started on
boot if `persistent=True`.

---

## 9. TUI rebuild — `textual`

The prototype's hand-rolled `tty`/`termios` rendering is replaced by
`textual` (chosen because: real widgets, real focus model, real
mouse support, snapshot-testable).

### Layout (one screen, responsive)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ AGENTS  opencode ●   hermes   goose   claude-code   …                       │  ← AgentStrip
├────────────────────────────────────────────────────────────────────────────┤
│  ╭─────────╮   ╭─────────╮   ╭─────────╮                                   │
│  │  RPM    │   │ TORQUE  │   │  FUEL   │    ⟵ large gauges (top hero row)   │
│  │  37%   │   │  62%   │   │ 4.1/8G  │                                    │
│  ╰─────────╯   ╰─────────╯   ╰─────────╯                                   │
├────────────────────────────────────────────────────────────────────────────┤
│  sparkline  ▁▂▃▅▇▆▄▂▁▂▃▅▇▆▄▂▁  (focused agent, last 5 min)               │
├────────────────────────────────────────────────────────────────────────────┤
│   PID    CPU%    MEM     THR   NI   R/s    W/s   STATE  COMMAND             │  ← ProcessTable
│  ▸1234   31.2%   812M    12    5    2.1K   0.4K   S     opencode …         │
│   …                                                                         │
├────────────────────────────────────────────────────────────────────────────┤
│ q quit · r refresh · c/m/p/n/i sort · ↑↓ select · ←→ switch agent ·        │  ← KeybindFooter
│ k kill · N nice · W weight · C cap · S install sensor · ? help             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Modal screens

- **Caps modal** (`C`) — form with CPU% / memory / weight / oom_policy.
- **Nice modal** (`N`) — single numeric input for selected process.
- **Sensor install modal** (`S`) — pick agent + mode + caps, preview the
  `systemd-run` command before confirming.
- **Help modal** (`?` or `F1`) — searchable keybind reference.

### Widget split

- `AgentStrip` — `Horizontal` of `Button`-like widgets, one per agent.
- `AnalogGauge` (TUI) — a `Widget` subclass using `Rich.canvas` or
  pure Unicode Braille/Block; the value is a reactive `float`.
- `ProcessTable` — wraps `DataTable`.
- `Sparkline` — small wrapper around `rich.sparkline.Sparkline`.
- `KeybindFooter` — static `Static` widget, updates on context.

State machine: `textual` App drives a `Sampler` on a 1s `Timer`; UI
binds to `Sampler.world` reactive.

---

## 10. GUI rebuild — PySide6

The `oplm-qt` prototype proves the gauge drawing works (`AnalogGauge`
in `oplm-qt:63`). The rebuild is a **proper layout**, not a `QVBoxLayout`
of widgets.

### Layout

```
MainWindow (QMainWindow, no menubar, no chrome)
└── QWidget (central)
    ├── HeaderBar (custom-painted, azrael wordmark in Inter Medium 18px)
    ├── GaugeRow (3 × AnalogGauge, fixed 220×220, equal spacing)
    ├── SecondaryReadoutRow (4 × small numeric panel: throttle%, OOM,
    │   threads, scope path)
    ├── SparklineRow (one per focused agent)
    ├── ProcessTable (QTableView with model, sortable headers)
    └── FooterBar (status text + keybind hints, custom-painted)
```

### `AnalogGauge` (GUI)

Lives in `azrael/gui/widgets/analog_gauge.py`. Same paint order as
§6.3. API:

```
class AnalogGauge(QWidget):
    value: float           # 0..100
    title: str
    unit: str              # "%" | "G" | "c"
    warn_at: float = 70.0
    crit_at: float = 90.0
    def set_value(self, v: float, *, fmt: str | None = None) -> None: ...
```

`fmt` lets the caller pass `"4.1G / 8.0G"` instead of `52%`.

The "bezel" is `paintEvent`-driven (not QSS) so we get pixel-exact
inset shadows and the inner gradient — QSS can't do that.

### Theming

`azrael.gui.theme` exposes a single `Theme` dataclass with the hex
values from §6.1. Both TUI and GUI pull from a single source of
truth in `azrael.config` — the TUI renders to ANSI 24-bit
(`\033[38;2;R;G;Bm`) when stdout is a TTY.

---

## 11. Data model

```python
# azrael/metrics/types.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class Caps:
    cpu_weight: int | None      # 1..10000; None = unchanged
    cpu_quota_pct: int | None   # 1..100*NCORES; None = unchanged
    memory_max: int | None      # bytes; None = unlimited
    memory_high: int | None     # bytes; None = unlimited
    nice: int | None            # -20..19; None = unchanged
    oom_policy: Literal["kill", "stop", "continue"] | None = None

@dataclass(frozen=True)
class Sample:
    timestamp: float            # monotonic
    cpu_pct: float              # 0..300 (vs quota)
    mem_used: int               # bytes
    mem_max: int | None
    throttle_pct: float         # 0..100
    oom_kills: int              # cumulative

@dataclass(frozen=True)
class Timeseries:
    agent_key: str
    samples: tuple[Sample, ...] # monotonic by construction

@dataclass(frozen=True)
class Scope:
    backend_name: str           # "linux_cgroup_v2"
    path: str                   # /sys/fs/cgroup/.../<unit>.scope
    leader_pid: int | None

@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    cmd: str
    state: str
    cpu_pct: float
    mem_rss: int
    nice: int
    threads: int
    io_rd_rate: float
    io_wr_rate: float

@dataclass(frozen=True)
class Agent:
    key: str                    # AgentDescriptor.key
    scope: Scope | None         # None if loose
    processes: tuple[Process, ...]
    sample: Sample
    caps: Caps                  # effective (or proposed if loose)
    sensor: Sensor | None

@dataclass(frozen=True)
class SystemMetrics:
    cores: int
    mem_total: int
    load1: float
    uptime_s: float

@dataclass(frozen=True)
class World:
    system: SystemMetrics
    agents: tuple[Agent, ...]
    timestamp: float
```

**Where state lives:**

- `Sampler` owns the rolling `prev_ticks` / `prev_io` dicts.
- `Sampler.history[agent_key]` is a `collections.deque(maxlen=N)`
  ring buffer of `Sample`.
- `Config` is loaded once at startup; caps the user sets are written
  back to `config.toml` on `azrael cap --save`.
- The TUI/GUI are **stateless** beyond selection. They render `World`
  and dispatch `Action` events (`Kill(pid)`, `SetCaps(scope, caps)`,
  `SwitchAgent(key)`) to the `Controller`.

---

## 12. Configuration — `~/.config/azrael/config.toml`

```toml
[ui]
theme = "garage"            # future: "track", "showroom"
refresh_ms = 1000
units = "binary"            # or "si"
start_screen = "tui"        # or "gui"

[agents.opencode]
caps = { cpu_weight = 100, memory_max = "4G", oom_policy = "continue" }

[agents.hermes]
caps = { cpu_weight = 50,  memory_max = "8G" }

[agents.claude-code]
mode = "monitor-only"       # refuse to write caps

[sensors.opencode]
persistent = true
mode = "control"

[backend]
prefer = "auto"             # or "linux_cgroup_v2", "windows_jobobj", "darwin"
fallback_to_loose = true

[history]
ring_size = 720             # 12 min at 1s
persist_path = "~/.local/share/azrael/history"
```

Loaded by `azrael.config.load()` into a frozen `Config` dataclass.
Validated by a small hand-written schema (no extra deps).

---

## 13. Packaging — `pyproject.toml`

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "azrael"
version = "0.1.0"
description = "TUI + GUI monitor and resource controller for AI agent harnesses"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
  "textual>=0.60,<1.0",
  "platformdirs>=4.2",
  "tomli>=2.0; python_version<'3.11'",
]

[project.optional-dependencies]
gui = ["PySide6>=6.6,<7.0"]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "hatchling>=1.21",
  "mypy>=1.10",
  "ruff>=0.5",
]
win = ["pywin32>=306; sys_platform=='win32'"]

[project.scripts]
azrael = "azrael.cli.main:main"

[project.urls]
Homepage = "https://example.invalid/azrael"

[tool.hatch.build.targets.wheel]
packages = ["src/azrael"]
```

Console scripts installed: `azrael` (default → tui), and the GUI
launches via `azrael gui` or the optional `azrael-gui` entrypoint
when the `gui` extra is installed.

Build: `python -m build` or `uv build`.

---

## 14. Testing strategy

### Unit tests (the bulk)

- `test_cgroup_parser.py` — fixture-driven; every `cpu.stat`,
  `memory.events`, `cpu.max`, `memory.pressure` shape we expect to
  see in the wild gets a fixture file and a parser test.
- `test_proc_stat_parser.py` — tricky edge cases: command names
  containing spaces, parentheses, `)`.
- `test_linux_backend.py` — mocks `pathlib.Path` via `pyfakefs`
  with a synthetic cgroup tree; asserts that `set_cpu_weight`
  writes `cpu.weight` correctly.
- `test_windows_backend.py` — mocks `pywin32` (`win32job`,
  `win32api`).
- `test_darwin_backend.py` — mocks `/proc`-equivalent (or rather
  just exercises `darwin.read_process_metrics` against a fixture).
- `test_registry.py` — descriptors loaded, fuzzy matches, ordering.
- `test_caps_parsing.py` — `parse_caps(["--cpu","50%","--mem","4G"])`.
- `test_sensor_install.py` — `subprocess.run` mocked; verify the
  exact `systemd-run --user --scope --unit=… --property=CPUWeight=…
  …` argv that azrael would use.

### TUI tests

- `textual.run_test()` snapshot tests against
  `DashboardScreen.compose()`. Asserts the `DataTable` rows, the
  gauge values, and the focused-agent badge.

### GUI tests

- `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui`.
- `AnalogGauge.paintEvent` is captured to a `QPixmap`, then we
  assert pixel hashes for representative `value` levels
  (0%, 35%, 75%, 95%) — catches unintended style regressions.

### Integration tests

- A `tests/integration/test_live_cgroup.py` is `@pytest.mark.skip`
  by default; runs only if `/sys/fs/cgroup/user.slice` exists and
  a fixture scope is mounted.

---

## 15. Phased delivery plan

| Phase | Milestone                                                                  | MVP? |
|------:|----------------------------------------------------------------------------|:----:|
| **1** | Repo skeleton: `pyproject.toml`, `src/` layout, `azrael --version` works   |  ✅   |
| **2** | `agents` module + `Registry` + built-in descriptors for all 9 agents      |  ✅   |
| **3** | `platforms.linux_cgroup_v2` backend (read-only) + cgroup fixture tests     |  ✅   |
| **4** | `metrics.Sampler` + `discovery` + per-process fallback for loose agents    |  ✅   |
| **5** | `cli.azrael` (TUI) using `textual` — gauges, process table, sort, kill     |  ✅   |
| **6** | `control`: `set_cpu_weight`, `set_memory_max`, `renice` via backend         |  ✅   |
| **7** | `control.sensor`: install / list / remove systemd `--user` scope           |      |
| **8** | `gui` app: PySide6 window + ported gauge widget + table                    |      |
| 9  | `platforms.windows_jobobj` (read + cap via Job Objects), best-effort darwin |      |
| 10 | First-run onboarding flow + `state.toml` persistence                       |      |
| 11 | History persistence (sqlite or append-only), sparklines in TUI/GUI        |      |
| 12 | Packaging: hatch build, `azrael` console script, `gui` extra               |      |
| 13 | CI (ruff + mypy + pytest on Linux), release to PyPI                        |      |

Phases 1–6 = MVP (a usable Linux TUI that discovers, monitors, and
caps agents). Phases 7–8 add the sensor install and GUI. Phases
9–13 are post-MVP.

---

## 16. What NOT to bring from the prototype

The prototype works; the rebuild is not throwing it away, but the
following patterns must **not** survive the rewrite:

1. **`getattr(main, '_scope_idx')` / `main._auto_cycle`** —
   module-level mutable state hanging off the `main` function.
   Replaced by a `Controller` dataclass owned by the App.
2. **Hand-rolled `tty`/`termios` + ANSI escape rendering** —
   replaced by `textual`. The TUI version of `AnalogGauge` may
   still use Braille/Block Unicode but inside a `textual.Widget`.
3. **Hardcoded `AGENTS = (...)` tuple** — replaced by `Registry`.
4. **Post-hoc `cpu_pct` injection into dicts** (`si["cpu_pct"] = …`
   scattered through `main`) — replaced by `Sampler` computing
   deltas once per tick into immutable `Sample` values.
5. **Mixed concerns in one file** — `oplm` does cgroup parsing,
   process parsing, *and* UI rendering in one 1133-line file.
   The split is enforced by the package layout in §4.
6. **`os.system("systemctl --user …")`** — replaced by
   `subprocess.run([...], check=True)` with captured stderr, so
   failures surface properly in the UI.
7. **`first_run` file as `Path(...).write_text("")`** — replaced by
   a real `state.toml` with a schema.
8. **History as a 30-line text file per agent, rewritten every
   tick** — replaced by an in-memory ring + on-disk append-only
   log with optional sqlite.
9. **Per-process rchar/wchar called "disk I/O" in comments** —
   the comment correctly notes it's page-cache-inclusive; the
   rebuild labels it as "I/O throughput" in the UI too.

---

## Appendix A — short code shapes

### A.1 `Registry` (sketch)

```python
class Registry:
    def __init__(self, descriptors: Iterable[AgentDescriptor]) -> None:
        self._by_key = {d.key: d for d in descriptors}

    def match_scope(self, scope_name: str) -> AgentDescriptor | None:
        # longest fragment wins (most specific)
        best: AgentDescriptor | None = None
        best_len = -1
        for d in self._by_key.values():
            for frag in d.scope_fragments:
                if frag in scope_name and len(frag) > best_len:
                    best, best_len = d, len(frag)
        return best

    def match_cmdline(self, cmdline: str) -> AgentDescriptor | None:
        low = cmdline.lower()
        best, best_len = None, -1
        for d in self._by_key.values():
            for n in d.cmdline_needles:
                if n in low and len(n) > best_len:
                    best, best_len = d, len(n)
        return best
```

### A.2 `ResourceBackend` (Linux sketch)

```python
class LinuxCgroupV2Backend:
    name = "linux_cgroup_v2"
    capabilities = frozenset({
        "cpu.weight", "memory.max", "memory.high", "sensor", "kill_scope"
    })

    def discover_scopes(self) -> list[Scope]:
        out: list[Scope] = []
        for base, dirs, _ in os.walk("/sys/fs/cgroup/user.slice"):
            for d in dirs:
                if d.endswith(".scope"):
                    out.append(Scope(self.name, os.path.join(base, d), None))
        return out

    def set_cpu_weight(self, scope: Scope, weight: int) -> None:
        if not 1 <= weight <= 10000:
            raise ValueError("cpu.weight must be 1..10000")
        (Path(scope.path) / "cpu.weight").write_text(f"{weight}\n")
```

### A.3 `Sampler` (sketch)

```python
class Sampler:
    def __init__(self, backend: ResourceBackend, registry: Registry,
                 interval_s: float = 1.0) -> None:
        self.backend, self.registry, self.interval = backend, registry, interval_s
        self._prev: dict[str, tuple[float, int]] = {}  # scope_key -> (t, cpu_usage_usec)
        self._ring: dict[str, deque[Sample]] = {}

    def tick(self) -> World:
        now = time.monotonic()
        agents: list[Agent] = []
        for scope in self.backend.discover_scopes():
            descriptor = self.registry.match_scope(Path(scope.path).name)
            if descriptor is None:
                continue
            m = self.backend.read_scope_metrics(scope)
            prev_t, prev_u = self._prev.get(scope.path, (now, m.cpu_usage_usec))
            dt = max(now - prev_t, 1e-6)
            cpu_pct = (m.cpu_usage_usec - prev_u) / 1e6 / dt / max(self.backend.capacity_cores(), 0.01) * 100
            self._prev[scope.path] = (now, m.cpu_usage_usec)
            sample = Sample(now, cpu_pct, m.mem_cur, m.mem_max, m.throttle_pct, m.oom_kill)
            self._ring.setdefault(descriptor.key, deque(maxlen=720)).append(sample)
            agents.append(Agent(descriptor.key, scope,
                                self._processes(scope), sample, Caps(), None))
        # loose process agents …
        return World(self._system(), tuple(agents), now)
```

---

## Appendix B — TUI keybinds (default)

| Key         | Action                                              |
|-------------|-----------------------------------------------------|
| `q`/`Esc`   | Quit                                                |
| `r`         | Force refresh                                       |
| `←` / `→`   | Switch focused agent                                |
| `↑` / `↓`   | Move row selection in process table                 |
| `c`/`m`/`p`/`n`/`i` | Sort by CPU / Mem / PID / Name / I/O        |
| `k`         | SIGTERM selected process                            |
| `K`         | Stop entire scope (confirm)                         |
| `N`         | Renice selected process (modal)                     |
| `W`         | Set scope `cpu.weight` (modal)                      |
| `C`         | Open caps editor for focused agent                  |
| `S`         | Install / manage sensor for focused agent           |
| `u`         | Toggle SI / binary units                            |
| `E`         | Export snapshot to `~/.local/share/azrael/snap.json`|
| `?` / `F1`  | Help modal                                          |
| `Ctrl-L`    | Redraw                                              |

---

## Appendix C — sample session

```bash
$ azrael                          # launches TUI
$ azrael gui                      # launches the Qt car-dashboard
$ azrael list-agents
opencode      2 scopes    CONTROL
hermes        1 scope     CONTROL
goose         0 scopes    LOOSE
claude-code   1 scope     MONITOR-ONLY
$ azrael watch --agent opencode --interval 1s
…live TTY output, Ctrl-C to stop
$ azrael cap --agent opencode --cpu-weight 200 --memory-max 6G
applied caps to scope user.slice/azrael-opencode-1234.scope
$ azrael install-sensor --agent hermes --mode control --memory-max 4G
installed persistent sensor azrael-hermes
$ azrael kill --scope user.slice/opencode-1234.scope
stopped scope (SIGTERM)
```

---

## 17. Repository, CI/CD, and landing page

Phase 0 decisions for hosting, building, and marketing the project.
All of these are concrete and ready to implement; nothing here is
"to be decided later".

### 17.1 Repository

- **Host**: GitHub.
- **Path**: `github.com/twistedoliver211fs-art/azrael` (public).
- **License**: MIT (`LICENSE` at repo root, standard MIT template).
- **Default branch**: `main`.
- **Local directory** keeps the misspelling `azrael/` for historical
  reasons; the product name and GitHub path are both `azrael`.

#### Create the repo from this directory

Run this **once**, from `/home/marvel/azrael/`, after the first commit
exists locally:

```bash
gh repo create twistedoliver211fs-art/azrael \
    --public \
    --source=. \
    --remote=origin \
    --push \
    --license=MIT \
    --description "TUI + GUI monitor and resource controller for AI agent harnesses"
```

The `--source=. --remote=origin --push` triple stages the existing
working tree, sets the `origin` remote, and pushes the initial commit
in one step. `--license=MIT` writes a `LICENSE` file if one is not
already present (it will be; the repo ships with one).

### 17.2 Toolchain

- **Package manager**: `poetry` (decision made; not `uv`, not
  `hatchling`).
- **Python**: `>=3.11,<3.14` (matrix tested on 3.11, 3.12, 3.13).
- **Linters / type-check**: `ruff` (lint + format) and `mypy` (strict
  on `src/azrael`).
- **Test runner**: `pytest` via `poetry run pytest`.
- **TUI**: `textual` (smoke-checked in CI with
  `poetry run textual --version`).
- **GUI**: `PySide6` (Qt 6 Python bindings).
- **Binary packaging**: `pyinstaller` (driven by CI, not local).

The `pyproject.toml` declares the above; `poetry install` reproduces
the dev environment exactly. Lockfile (`poetry.lock`) is committed.

### 17.3 Landing page

- **Framework**: [Astro](https://astro.build) (static site, zero JS by
  default, fast).
- **Location**: `landing/` at the repo root, sibling of `src/`.
- **Hosting**: Vercel (project imported once, then driven entirely by
  the GitHub Action below — no Vercel-side GitHub app needed).
- **Build/deploy command**: `npx vercel deploy --prod --yes --token $VERCEL_TOKEN`
  (Vercel deploys prebuilt static output; no build hook required).
- **Auth**: the `VERCEL_TOKEN` secret is a personal access token
  generated in Vercel account settings, stored as a GitHub Actions
  repository secret named `VERCEL_TOKEN`. No team token, no Vercel
  GitHub App.

#### Brand palette (shared with the product)

The landing site **must** use the same car-dashboard palette as the
TUI/GUI so marketing and product feel like one brand:

| Token             | Hex       | Used for                               |
|-------------------|-----------|----------------------------------------|
| `--bg`            | `#1b1816` | Page background, hero, cards           |
| `--amber`         | `#e8c178` | Primary accent, headings, primary CTA  |
| `--red`           | `#c63a3a` | Alerts, "kill" actions, error states   |
| `--ink`           | `#f5ecd9` | Body text on `--bg`                    |
| `--mute`          | `#7a6f63` | Secondary text, borders, dividers      |

These five tokens are defined once in `landing/src/styles/tokens.css`
and reused everywhere. The TUI/GUI source reads the same hex values
from a shared `azrael.theme` module so the colors literally match
across surfaces.

### 17.4 CI/CD — GitHub Actions

All workflows live under `.github/workflows/`. Three files, one job
each, no matrix sprawl.

#### `ci.yml` — continuous integration

- **Triggers**: `push` to `main`, and every `pull_request` targeting
  `main`.
- **Runner**: `ubuntu-latest`.
- **Steps**:
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` with the python-version matrix
     `[3.11, 3.12, 3.13]`.
  3. `pipx install poetry` (or the official `snok/install-poetry`
     action pinned to a version).
  4. `poetry install --with dev` (caches via `actions/cache` keyed on
     `pyproject.toml` + `poetry.lock`).
  5. `poetry run pytest -q`
  6. `poetry run ruff check`
  7. `poetry run mypy src/azrael`
  8. `poetry run textual --version` (smoke import check)
- A failure on any step fails the PR / blocks merge.

#### `release.yml` — tagged releases + binaries

- **Trigger**: `push` of a tag matching `v*` (e.g. `v0.1.0`).
- **Runner**: `ubuntu-latest` (cross-compile via PyInstaller; PyInstaller
  is per-target but a Linux runner can produce Linux binaries natively
  and macOS/Windows binaries via the official PyInstaller Docker images
  or by using the matching GitHub-hosted runner for each target).
- **Targets** (one job per OS/arch):

  | OS       | Arch    | Artifact name             |
  |----------|---------|---------------------------|
  | linux    | amd64   | `azrael-vX.Y.Z-linux-x86_64` |
  | linux    | arm64   | `azrael-vX.Y.Z-linux-aarch64` |
  | macos    | amd64   | `azrael-vX.Y.Z-macos-x86_64` |
  | macos    | arm64   | `azrael-vX.Y.Z-macos-arm64` |
  | windows  | amd64   | `azrael-vX.Y.Z-windows-x86_64.exe` |

- **GUI variants**: each target above also produces a `-gui` variant
  (`azrael-vX.Y.Z-linux-x86_64-gui`, etc.) that bundles the Qt GUI
  entry point instead of the TUI one. The GUI binary is built from the
  same PyInstaller spec with a different `--name` and entry script.
- **Upload**: `softprops/action-gh-release@v2` attaches every artifact
  to the GitHub Release created by the tag push.
- **No PyPI publish in v1.** Source lives on GitHub; binaries are the
  install path.

#### `landing.yml` — deploy the marketing site

- **Trigger**: `push` to `main` **and** any path under `landing/**`
  changed (use `paths:` filter to skip pure-Python commits).
- **Runner**: `ubuntu-latest`.
- **Steps**:
  1. `actions/checkout@v4`
  2. `actions/setup-node@v4` with `node-version: 20`.
  3. `working-directory: landing` →
     `npm ci`
  4. Same dir → `npx vercel deploy --prod --yes --token $VERCEL_TOKEN`
- The `VERCEL_TOKEN` secret is read from repository secrets; no
  environment, no project id needed for this command form.

### 17.5 What v1 ships

| Surface         | Where                                                 |
|-----------------|-------------------------------------------------------|
| Source          | `github.com/twistedoliver211fs-art/azrael`                            |
| Pre-built bins  | GitHub Releases (5 OS/arch × 2 modes = 10 artifacts)  |
| Landing page    | Vercel (URL printed by the first `landing.yml` run)   |
| Docs site       | Same Astro project, `/docs` route, same palette      |
| PyPI            | **Not published in v1.** Resurfaces in v2 if demand.   |

