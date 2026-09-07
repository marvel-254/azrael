"""Tests for `azrael.control.caps` — pure parsers and formatters."""

from __future__ import annotations

import pytest

from azrael.agents.descriptor import Caps
from azrael.control.caps import (
    caps_from_kwargs,
    format_bytes,
    format_cpu_weight,
    parse_cpu_weight,
    parse_memory,
    parse_nice,
)


class TestParseCpuWeight:
    @pytest.mark.parametrize("raw", ["1", "100", "200", "10000"])
    def test_parse_cpu_weight_valid(self, raw: str) -> None:
        assert parse_cpu_weight(raw) == int(raw)

    @pytest.mark.parametrize("raw", ["0", "10001", "-1", "abc", "", "  "])
    def test_parse_cpu_weight_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            parse_cpu_weight(raw)


class TestParseMemory:
    def test_parse_memory_basic(self) -> None:
        assert parse_memory("0") == 0
        assert parse_memory("1024K") == 1024 * 1024
        assert parse_memory("512M") == 512 * 1024 * 1024
        assert parse_memory("4G") == 4 * 1024**3

    @pytest.mark.parametrize("raw", ["unlimited", "max", "inf"])
    def test_parse_memory_unlimited(self, raw: str) -> None:
        assert parse_memory(raw) == -1

    @pytest.mark.parametrize("raw", ["4X", "abc", "", "-1"])
    def test_parse_memory_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            parse_memory(raw)


class TestParseNice:
    @pytest.mark.parametrize("raw,expected", [("-20", -20), ("0", 0), ("19", 19)])
    def test_parse_nice_valid(self, raw: str, expected: int) -> None:
        assert parse_nice(raw) == expected

    @pytest.mark.parametrize("raw", ["-21", "20", "abc", ""])
    def test_parse_nice_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            parse_nice(raw)


class TestFormatBytes:
    def test_format_bytes_binary(self) -> None:
        assert format_bytes(4 * 1024**3) == "4.0G"
        assert format_bytes(512 * 1024**2) == "512.0M"

    @pytest.mark.parametrize("value", [None, -1])
    def test_format_bytes_unlimited(self, value: int | None) -> None:
        assert format_bytes(value) == "unlimited"


class TestFormatCpuWeight:
    def test_format_cpu_weight_unset(self) -> None:
        assert format_cpu_weight(None) == "unset"

    def test_format_cpu_weight_set(self) -> None:
        assert format_cpu_weight(200) == "200 (default 100)"


class TestCapsFromKwargs:
    def test_caps_from_kwargs_cpu_weight_only(self) -> None:
        caps = caps_from_kwargs(cpu_weight="200")
        assert caps == Caps(
            cpu_weight=200,
            memory_max=None,
            memory_high=None,
            nice=None,
            oom_policy=None,
        )

    def test_caps_from_kwargs_all_fields(self) -> None:
        caps = caps_from_kwargs(
            cpu_weight="100",
            memory_max="4G",
            memory_high="2G",
            nice="5",
            oom_policy="kill",
        )
        assert caps.cpu_weight == 100
        assert caps.memory_max == 4 * 1024**3
        assert caps.memory_high == 2 * 1024**3
        assert caps.nice == 5
        assert caps.oom_policy == "kill"

    def test_caps_from_kwargs_empty(self) -> None:
        assert caps_from_kwargs() == Caps()

    def test_caps_from_kwargs_bad_input_raises(self) -> None:
        with pytest.raises(ValueError):
            caps_from_kwargs(cpu_weight="99999")
        with pytest.raises(ValueError):
            caps_from_kwargs(memory_max="4X")
        with pytest.raises(ValueError):
            caps_from_kwargs(oom_policy="bad")

    def test_caps_from_kwargs_memory_unlimited(self) -> None:
        caps = caps_from_kwargs(memory_max="unlimited")
        assert caps.memory_max == -1
