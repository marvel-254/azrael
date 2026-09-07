# azrael

azrael is a TUI + GUI monitor and resource controller for AI agent harnesses. It discovers the agents running on your box (opencode, hermes, goose, claude-code, cline, and friends), reads their cgroup/Job-Object resource usage, and lets you cap CPU weight and memory with the same confidence you'd cap a runaway Docker container — all behind a deliberately opinionated "car dashboard" interface, not another SaaS tile grid.

![dashboard hero placeholder — screenshot goes here](docs/screenshots/hero.png)

## What it is

azrael sits between you and the half-dozen AI agents you have running locally. It shows you what each one is costing you in CPU and RAM right now, and — on Linux — lets you push caps into the kernel via cgroup v2 so an agent that decides to fork-bomb the box can't. It ships with both a keyboard-first TUI (built on `textual`) and a Qt GUI (built on PySide6) so you can pick the surface that fits the moment.

## Features

- **Discover** running agent harnesses by cgroup scope first, `/proc/<pid>/cmdline` fallback second.
- **Measure** per-agent CPU%, RSS, cgroup `memory.current`/`memory.max`, throttle time, OOM kills, and the full process tree under each scope.
- **Display** the data as a deliberately-designed *car dashboard* — large round gauges, warm "garage" palette, real numerals — not a generic card grid.
- **Control** per-agent resource caps: cgroup `cpu.weight`, `memory.max`/`memory.high`, and per-process `nice` (when cgroup is not available).
- **Install sensors** — wrap unwrapped ("loose") agents in a `systemd --user` scope so azrael can both monitor *and* control them.
- **Work** identically across Linux (cgroup v2, primary), Windows (Job Objects, secondary), and macOS (best-effort, monitor-only by design).

## Install

The package will be published to PyPI once v1 is tagged. For now, install from source with Poetry:

```bash
git clone https://github.com/twistedoliver211fs-art/azrael
cd azrael
poetry install --all-extras        # TUI + GUI + dev deps
poetry run azrael --help
```

If/when published:

```bash
pip install azrael[all]            # TUI + GUI extras
```

### Build from source

```bash
poetry build                       # produces dist/azrael-0.1.0.tar.gz and *.whl
poetry run pip install dist/azrael-0.1.0-py3-none-any.whl
```

## Quick start

```bash
# Launch the TUI (default)
azrael

# Launch the Qt car-dashboard GUI
azrael gui

# List detected agents and whether azrael can control them
azrael list-agents
```

The first run creates `~/.config/azrael/config.toml` with sensible defaults — see `PLAN.md` §12 for the schema.

## Supported agents

azrael ships with built-in descriptors for the following agent harnesses (each is matched by cgroup scope fragment and `/proc` cmdline needle — see `PLAN.md` §2):

- `opencode`
- `hermes`
- `kilo-code`
- `openclaw`
- `goose`
- `claude-code`
- `openclaude`
- `cline`
- `freebuff`

Adding your own is a single TOML file under `~/.config/azrael/agents/<name>.toml` — no code change required.

## Platform support

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

macOS is **monitor-only** by design (see `PLAN.md` §1 non-goals). The seam is `azrael.platforms.ResourceBackend` — see `PLAN.md` §5.

## Development

```bash
poetry install --all-extras                # install everything (TUI + GUI + dev)
poetry run pytest                          # run the test suite
poetry run ruff check                      # lint
poetry run ruff format                     # auto-format
poetry run mypy src/azrael                 # strict type-check on the source tree
```

Tests live under `tests/`; fixtures under `tests/fixtures/`. See `PLAN.md` §14 for the testing strategy.

## License

MIT — see [LICENSE](LICENSE).

## Links

- Landing page: <https://azrael-landing-mlc8x85mg-twistedoliver211fs-1271.vercel.app>
- Repository: <https://github.com/twistedoliver211fs-art/azrael>
- Design plan: [PLAN.md](PLAN.md)
