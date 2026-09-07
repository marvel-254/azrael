# AGENTS.md

Contributor guide for azrael — written for both human contributors and AI coding agents. The shortest path to "this codebase makes sense" is in this file. For full design rationale and tradeoffs, see [`PLAN.md`](PLAN.md).

## Project layout

```
azrael/
├── pyproject.toml          # Poetry project, deps, lint/format/type/test config
├── README.md               # user-facing intro, install, quick start
├── PLAN.md                 # the design document (read this for "why")
├── AGENTS.md               # this file
├── LICENSE                 # MIT
├── src/azrael/             # the package
│   ├── version.py          # single source of truth for __version__
│   ├── errors.py           # agent-log error scan
│   ├── config.py           # ~/.config/azrael/config.toml loader
│   ├── agents/             # identity seam — descriptor + registry
│   ├── platforms/          # OS seam — ResourceBackend Protocol + per-OS impls
│   ├── metrics/            # time seam — Sampler + types
│   ├── discovery/          # walks cgroup trees + /proc cmdlines, unifies
│   ├── control/            # caps, actions, sensor install
│   ├── history/            # ring buffer + on-disk log
│   ├── tui/                # textual app + screens + widgets
│   ├── gui/                # PySide6 app + windows + widgets
│   └── cli/                # click/argparse top-level + subcommands
├── tests/                  # pytest, mirrors src/azrael
├── landing/                # Astro marketing site (separate scaffold)
└── .github/workflows/      # ci.yml, release.yml, landing.yml (separate scaffold)
```

`PLAN.md` §4 has the canonical layout; if you're adding a module, put it in the slot that matches its seam.

## Architecture deep seams

azrael has three **deep modules** — small interfaces that hide the most non-decision complexity. Everything else hangs off them.

- **`platforms.ResourceBackend`** (OS seam, `PLAN.md` §5.1) — every other module needs to *do something* to a process or a container. Concentrating all OS-specific logic here (cgroup v2 on Linux, Job Objects on Windows, ulimit on macOS) means the rest of the codebase is portable by construction. Adding a new OS = adding one file under `azrael/platforms/`.
- **`agents.Registry`** (identity seam, `PLAN.md` §5.2) — the UI and sampler call `registry.match_scope(name)` / `registry.match_cmdline(cmd)` and never hardcode agent names. Adding a new agent = dropping one TOML file under `~/.config/azrael/agents/`, no code change.
- **`metrics.Sampler`** (time seam, `PLAN.md` §5.3) — the only thing that calls `time.monotonic()` and owns rolling state. Everything else receives **immutable `Sample` snapshots**. This is what makes the TUI and GUI deterministically testable.

If a change isn't routed through one of these three, it's probably in the wrong place.

## Design language

The product's aesthetic spec lives in `PLAN.md` §6. The **hard rules** (enforced by code, not taste) are:

1. **No rounded card-with-shadow kits.** Cards, if used, are square with 1px `--wire` border. No `border-radius: 12px; box-shadow`.
2. **No ALL-CAPS eyebrow labels.** Section titles are sentence-case Inter Medium, never `UPPERCASE TRACKED`.
3. **No decorative gradient washes.** The only gradients are *inside* the gauge (the warning arc) and the bezel inner-glow.
4. **No emoji as UI icons.** The needle, the tick, the center dot — these are the icons.
5. **The gauges are the hero.** Everything else is information density below them.
6. **Color means something.** `--needle-crit` only fires above 90%. `--accent` only when the value is in its safe range. Color is never used for decoration.

Palette tokens (exact hex) are in `PLAN.md` §6.1. The TUI, GUI, and the landing site all read from the same shared values — do not introduce a second palette.

## Style

- **`poetry run ruff check`** — lints. CI runs this.
- **`poetry run ruff format`** — auto-formats. Line length 100, double quotes, spaces.
- **`poetry run mypy src/azrael`** — strict mode on the source tree only (`disallow_untyped_defs = true`).
- **`poetry run pytest`** — tests live under `tests/`, mirror the `src/azrael/` package layout.

Every Python file under `src/azrael/` must type-check under `mypy --strict`. New modules must ship with tests in the same PR.

## What NOT to do

The rebuild is throwing away nine specific patterns from the prototype (`PLAN.md` §16). Do not reintroduce them:

1. **No module-level mutable state on `main`**. No `getattr(main, '_scope_idx')`, no `main._auto_cycle`. Use a `Controller` dataclass owned by the App.
2. **No hand-rolled `tty`/`termios` + ANSI rendering**. Use `textual`. Unicode Braille/Block is fine *inside* a `textual.Widget`.
3. **No hardcoded `AGENTS = (...)` tuple**. Use `Registry` and the TOML user files.
4. **No post-hoc dict mutation** (`si["cpu_pct"] = …`). The `Sampler` computes deltas once per tick into immutable `Sample` values.
5. **No kitchen-sink files**. Don't re-create the 1133-line `oplm.py`. Split by seam.
6. **No `os.system("systemctl --user …")`**. Use `subprocess.run([...], check=True)` with captured stderr.
7. **No `Path(...).write_text("")` as a "first run" sentinel**. Use a real `state.toml` with a schema.
8. **No 30-line text file rewritten every tick for history**. Use an in-memory `deque(maxlen=N)` ring + on-disk append-only log.
9. **No labelling page-cache `rchar`/`wchar` as "disk I/O" in code paths** without the disclosure comment. The UI must label it "I/O throughput".

## Commands

```bash
poetry install --all-extras         # everything (TUI + GUI + dev)
poetry run pytest                   # test suite
poetry run azrael                   # launch the TUI
poetry run azrael gui               # launch the Qt GUI
poetry run azrael list-agents       # show detected agents and their mode
poetry run ruff check && poetry run mypy src/azrael   # pre-commit sanity
```
