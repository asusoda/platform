"""The guardrail table in core/tools.py: one row for each tool, and rows that agree with the tools."""

import pytest

from core import limits, tools
from modules import manifest


@pytest.fixture(scope="module", autouse=True)
def loaded():
    manifest.load_tools()


def test_every_tool_has_a_row_and_every_row_names_a_tool():
    assert set(tools.TOOLS) == set(tools.GUARDRAILS)


def test_a_tool_behind_a_read_scope_does_not_write():
    wrong = [name for name, spec in tools.TOOLS.items() if spec.scope.endswith(":read") and spec.guard.writes]
    assert wrong == []


def test_the_spec_takes_its_rules_from_the_row():
    for name, spec in tools.TOOLS.items():
        row = tools.GUARDRAILS[name]
        assert spec.guard is row
        assert spec.read_only is (not row.writes)
        assert ("confirm" in spec.input_schema.get("properties", {})) is row.confirm, name


def test_a_tool_without_a_row_cannot_register():
    with pytest.raises(ValueError, match="Add nope.tool to GUARDRAILS"):
        tools.tool("nope.tool", description="x", scope="org:read")


def test_confirm_only_with_a_write_and_known_rate_classes():
    with pytest.raises(ValueError):
        tools.Guardrail(writes=False, confirm=True)
    with pytest.raises(ValueError):
        tools.Guardrail(writes=True, rate="fast")


def test_each_rate_class_with_a_limit_is_declared():
    for rate, value in tools.RATES.items():
        key = tools.rate_limit(rate)
        if value is None:
            assert key is None
        else:
            assert key in limits.LIMITS and limits.LIMITS[key].window == "minute"


def test_reads_that_the_scope_name_got_wrong_are_reads_now():
    # These sit behind a manage scope but only read; MCP clients see them as read-only
    for name in ("access.tokens", "access.secrets", "godfather.pods", "feeds.list"):
        assert tools.TOOLS[name].read_only, name
