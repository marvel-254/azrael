"""azrael CLI entry point.

Subcommands (per PLAN Appendix C):

- `azrael` / `azrael tui` — launch the Textual TUI (default).
- `azrael gui` — GUI (Phase 8, raises NotImplementedError for now).
- `azrael list-agents` — table of detected descriptors.
- `azrael watch --agent KEY --interval 1.0` — non-TUI live view.
- `azrael cap --agent KEY [--cpu-weight N] [--memory-max BYTES]`.
- `azrael kill --pid N | --scope PATH`.
- `azrael install-sensor --agent KEY --cmd "..."` — stub for Phase 7.
"""

from __future__ import annotations

import signal
import sys
import time

import click

from azrael.agents.registry import Registry
from azrael.control import applier as control_applier
from azrael.control import caps as control_caps
from azrael.metrics.sampler import Sampler
from azrael.platforms.backend import ResourceBackend, detect
from azrael.version import __version__


def _make_registry() -> Registry:
    return Registry.discover()


def _make_backend_or_die() -> ResourceBackend:
    try:
        return detect()
    except RuntimeError as exc:
        click.echo(f"azrael: {exc}", err=True)
        sys.exit(2)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "--version", "-V")
def main() -> None:
    """azrael — TUI + GUI monitor and resource controller for AI agent harnesses."""


@main.command("tui")
def tui() -> None:
    """Launch the Textual TUI (default)."""
    try:
        from azrael.tui import AzraelApp
    except ImportError as exc:
        raise click.ClickException(f"tui dependencies not installed: {exc}") from exc
    registry = _make_registry()
    backend = _make_backend_or_die()
    sampler = Sampler(backend, registry)
    AzraelApp(sampler, backend).run()


@main.command("gui")
def gui() -> None:
    """Launch the Qt car-dashboard GUI (Phase 8)."""
    raise click.ClickException("Phase 8: the PySide6 GUI is not implemented yet.")


@main.command("list-agents")
def list_agents() -> None:
    """Print the detected agents as a table."""
    registry = _make_registry()
    rows = []
    for d in registry.all():
        logs = ", ".join(str(p) for p in d.user_log_paths) or "-"
        rows.append((d.key, d.display_name, logs, d.website or "-"))
    if not rows:
        click.echo("no descriptors registered")
        return
    # click 8 has tabulate? no — emit a simple fixed-width table manually.
    key_w = max(len(r[0]) for r in rows)
    name_w = max(len(r[1]) for r in rows)
    log_w = max(len(r[2]) for r in rows)
    click.echo(f"{'KEY'.ljust(key_w)}  {'NAME'.ljust(name_w)}  {'LOG_PATHS'.ljust(log_w)}  WEBSITE")
    for key, name, logs, website in rows:
        click.echo(f"{key.ljust(key_w)}  {name.ljust(name_w)}  {logs.ljust(log_w)}  {website}")


@main.command("watch")
@click.option("--agent", "agent_key", required=True, help="Agent descriptor key (e.g. opencode)")
@click.option(
    "--interval", default=1.0, type=float, show_default=True, help="Seconds between samples"
)
def watch(agent_key: str, interval: float) -> None:
    """Print a 1-line live update per interval. Ctrl-C exits."""
    registry = _make_registry()
    backend = _make_backend_or_die()
    sampler = Sampler(backend, registry)

    stop = {"flag": False}

    def _handler(_sig: int, _frame: object) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handler)

    click.echo(f"watching {agent_key} every {interval}s — press Ctrl-C to stop")
    while not stop["flag"]:
        try:
            agents = sampler.tick()
        except Exception as exc:
            click.echo(f"error: {exc}", err=True)
            break
        target = next((a for a in agents if a.key == agent_key), None)
        if target is None:
            click.echo(f"[{time.strftime('%H:%M:%S')}] no scope matched '{agent_key}'")
        else:
            s = target.sample
            click.echo(
                f"[{time.strftime('%H:%M:%S')}] "
                f"cpu {s.cpu_pct:5.1f}%  mem {_fmt_bytes(s.mem_used)}  "
                f"throttle {s.throttle_pct:5.1f}%  oom {s.oom_kills}"
            )
        # interruptible sleep
        end = time.monotonic() + interval
        while not stop["flag"] and time.monotonic() < end:
            time.sleep(min(0.1, end - time.monotonic()))


@main.command("cap")
@click.option("--agent", "agent_key", required=True, help="Agent descriptor key")
@click.option("--cpu-weight", type=int, default=None, help="cpu.weight 1..10000")
@click.option("--memory-max", default=None, help="memory.max (e.g. 4G, 'unlimited')")
@click.option("--memory-high", default=None, help="memory.high (e.g. 6G, 'unlimited')")
@click.option("--nice", type=int, default=None, help="process nice (-20..19, per-process)")
@click.option(
    "--oom-policy",
    type=click.Choice(["kill", "stop", "continue"]),
    default=None,
    help="memory.oom.group policy",
)
def cap(
    agent_key: str,
    cpu_weight: int | None,
    memory_max: str | None,
    memory_high: str | None,
    nice: int | None,
    oom_policy: str | None,
) -> None:
    """Apply caps to an agent's scope via `control.applier.apply_caps`."""
    if (
        cpu_weight is None
        and memory_max is None
        and memory_high is None
        and nice is None
        and oom_policy is None
    ):
        raise click.UsageError(
            "at least one of --cpu-weight / --memory-max / --memory-high "
            "/ --nice / --oom-policy is required"
        )
    registry = _make_registry()
    backend = _make_backend_or_die()
    if registry.get(agent_key) is None:
        raise click.ClickException(f"unknown agent: {agent_key}")
    sampler = Sampler(backend, registry)
    agents = sampler.tick()
    target = next((a for a in agents if a.key == agent_key), None)
    if target is None:
        raise click.ClickException(f"no active scope for '{agent_key}'")
    if target.scope is None:
        raise click.ClickException(f"'{agent_key}' has no cgroup scope (loose process)")

    # `nice` and `oom_policy` are per-process / future-fanout; the
    # applier handles scope caps only. Report them eagerly so the user
    # sees what was requested.
    if nice is not None:
        try:
            parsed_nice = control_caps.parse_nice(str(nice))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"would renice pid <each in scope> → {parsed_nice} (per-process)")
    if oom_policy is not None:
        click.echo(f"would set memory.oom.group policy = {oom_policy} (not yet wired)")

    try:
        caps = control_caps.caps_from_kwargs(
            cpu_weight=str(cpu_weight) if cpu_weight is not None else None,
            memory_max=memory_max,
            memory_high=memory_high,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if caps.cpu_weight is None and caps.memory_max is None and caps.memory_high is None:
        return

    results = control_applier.apply_caps(backend, target.scope, caps)
    if not results:
        click.echo("no caps applied (all requested fields were unset)")
        return
    failed = 0
    for r in results:
        if r.ok:
            click.echo(f"ok  {r.message}")
        else:
            failed += 1
            click.echo(f"err {r.error}", err=True)
    if failed:
        raise click.ClickException(f"{failed} cap(s) failed")


@main.command("kill")
@click.option("--pid", type=int, default=None, help="PID to SIGTERM")
@click.option("--scope", default=None, help="cgroup scope path to stop")
def kill(pid: int | None, scope: str | None) -> None:
    """Kill a process or stop a whole scope via `control.actions`."""
    if pid is None and scope is None:
        raise click.UsageError("specify --pid or --scope")
    backend = _make_backend_or_die()
    from azrael.control import actions as control_actions
    from azrael.platforms._common import Scope

    if pid is not None:
        r = control_actions.kill_pid(backend, pid)
        if not r.ok:
            raise click.ClickException(r.error or "kill_pid failed")
        click.echo(r.message)
        return
    scope_obj = Scope(backend.name, scope or "", None)
    r = control_actions.kill_scope(backend, scope_obj)
    if not r.ok:
        raise click.ClickException(r.error or "kill_scope failed")
    click.echo(r.message)


@main.command("install-sensor")
@click.option("--agent", "agent_key", required=True, help="Agent descriptor key")
@click.option("--cmd", "cmdline", required=True, help="Command line to wrap")
def install_sensor(agent_key: str, cmdline: str) -> None:
    """Install a sensor for an agent (Phase 7)."""
    registry = _make_registry()
    descriptor = registry.get(agent_key)
    if descriptor is None:
        raise click.ClickException(f"unknown agent: {agent_key}")
    if descriptor.sensor_template is None:
        raise click.ClickException(f"agent {agent_key!r} has no sensor_template")
    cmd_text = descriptor.sensor_template.format(key=agent_key, cmd=cmdline)
    click.echo("coming soon (Phase 7). For now, run:")
    click.echo(f"  {cmd_text}")


def _fmt_bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "K", "M", "G", "T"):
        if f < 1024 or unit == "T":
            if unit == "B":
                return f"{int(f)}B"
            return f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}T"


if __name__ == "__main__":  # pragma: no cover
    main()
