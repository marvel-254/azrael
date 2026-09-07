from __future__ import annotations

from pathlib import Path

from azrael.agents.descriptor import AgentDescriptor, Caps

_SENSOR_TEMPLATE = "systemd-run --user --scope --unit=azrael-{key} {cmd}"

_HOMEDIR_CONFIG: dict[str, tuple[str, str]] = {
    "opencode": ("~/.config/opencode/logs", "~/.config/opencode"),
    "hermes": ("~/.hermes/logs", "~/.hermes"),
    "kilo-code": ("~/.config/kilo/logs", "~/.config/kilo"),
    "openclaw": ("~/.config/openclaw/logs", "~/.config/openclaw"),
    "goose": ("~/.config/goose/logs", "~/.config/goose"),
    "claude-code": ("~/.claude/logs", "~/.claude"),
    "openclaude": ("~/.config/openclaude/logs", "~/.config/openclaude"),
    "cline": ("~/.config/cline/logs", "~/.config/cline"),
    "freebuff": ("~/.config/freebuff/logs", "~/.config/freebuff"),
}

_AGENT_INFO: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], str]] = {
    "opencode": (
        "OpenCode",
        ("opencode",),
        ("opencode", ".scope"),
        "https://opencode.ai",
    ),
    "hermes": (
        "Hermes",
        ("hermes",),
        ("hermes", ".scope"),
        "https://github.com/just-every/hermes-agent",
    ),
    "kilo-code": (
        "Kilo Code",
        ("kilo-code", "kilo_code", "kilocode"),
        ("kilo-code", "kilocode", ".scope"),
        "https://kilocode.ai",
    ),
    "openclaw": (
        "OpenClaw",
        ("openclaw",),
        ("openclaw", ".scope"),
        "https://github.com/openclaw/openclaw",
    ),
    "goose": (
        "Goose",
        ("goose",),
        ("goose", ".scope"),
        "https://block.github.io/goose/",
    ),
    "claude-code": (
        "Claude Code",
        ("claude-code", "claude_code", "claude code", "@anthropic-ai/claude-code"),
        ("claude-code", "claude_code", "claude", ".scope"),
        "https://claude.com/product/claude-code",
    ),
    "openclaude": (
        "OpenClaude",
        ("openclaude",),
        ("openclaude", ".scope"),
        "https://github.com/openclaude/openclaude",
    ),
    "cline": (
        "Cline",
        ("cline",),
        ("cline", ".scope"),
        "https://cline.bot",
    ),
    "freebuff": (
        "Freebuff",
        ("freebuff",),
        ("freebuff", ".scope"),
        "https://github.com/freebuff/freebuff",
    ),
}


def _build(key: str) -> AgentDescriptor:
    display, needles, fragments, website = _AGENT_INFO[key]
    log_str, cfg_str = _HOMEDIR_CONFIG[key]
    return AgentDescriptor(
        key=key,
        display_name=display,
        cmdline_needles=needles,
        scope_fragments=fragments,
        user_log_paths=(Path(log_str),),
        config_path_hints=(Path(cfg_str),),
        default_caps=Caps(),
        sensor_template=_SENSOR_TEMPLATE,
        website=website,
    )


builtin_descriptors: tuple[AgentDescriptor, ...] = tuple(_build(k) for k in _AGENT_INFO)


__all__ = ["builtin_descriptors"]
