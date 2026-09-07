"""Tests for the AnalogGauge widget."""

from __future__ import annotations

from azrael.tui.widgets.gauge import AnalogGauge


def _render_text(g: AnalogGauge) -> str:
    return g._render_str()


def test_gauge_default_zero() -> None:
    g = AnalogGauge("Rpm")
    g.set_value(0.0)
    rendered = _render_text(g)
    # Label row contains the title and "0.0%"
    assert "Rpm" in rendered
    assert "0.0%" in rendered


def test_gauge_set_value_updates_render() -> None:
    g = AnalogGauge("Rpm")
    g.set_value(50.0)
    rendered = _render_text(g)
    assert "50.0%" in rendered


def test_gauge_value_out_of_range_clamped() -> None:
    g = AnalogGauge("Rpm")
    g.set_value(200.0)
    # No exception; render still produces a string.
    rendered = _render_text(g)
    assert "100.0%" in rendered


def test_gauge_needle_color_at_thresholds() -> None:
    g = AnalogGauge("Rpm", warn_at=70.0, crit_at=90.0)
    assert g._needle_color(95) == g._theme.needle_crit
    assert g._needle_color(75) == g._theme.needle_warn
    assert g._needle_color(50) == g._theme.needle


def test_gauge_render_contains_arc() -> None:
    g = AnalogGauge("Rpm")
    rendered = _render_text(g)
    assert "╭" in rendered
    assert "╮" in rendered
    assert "│" in rendered
    assert "▲" in rendered
