"""The tool surface is fixed: five named tools, annotations, typed outputs, stable listing."""

import pytest
from fastmcp import Client, FastMCP

from buddy_mcp.models import TOOL_NAMES

pytestmark = pytest.mark.anyio

CONTENT_TOOLS = ("handbook_get", "handbook_search", "guides_search", "guides_get_section")
GAP_TOOL = "buddy_report_gap"


async def test_exactly_the_five_named_tools(server: FastMCP) -> None:
    async with Client(server) as client:
        tools = await client.list_tools()
    assert sorted(tool.name for tool in tools) == sorted(TOOL_NAMES)
    assert len(tools) == 5


async def test_every_tool_has_an_object_output_schema_and_a_real_description(
    server: FastMCP,
) -> None:
    async with Client(server) as client:
        tools = await client.list_tools()
    for tool in tools:
        assert tool.output_schema is not None, tool.name
        assert tool.output_schema.get("type") == "object", tool.name
        assert tool.description is not None and len(tool.description) > 40, tool.name


async def test_descriptions_tell_the_model_what_a_miss_means_and_what_to_call_next(
    server: FastMCP,
) -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    for name in CONTENT_TOOLS:
        assert "no_results" in (tools[name].description or ""), name
    for name in ("handbook_search", "guides_search"):
        assert GAP_TOOL in (tools[name].description or ""), name


async def test_only_the_gap_tool_is_not_read_only(server: FastMCP) -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    writers = [
        name
        for name, tool in tools.items()
        if tool.annotations is not None and tool.annotations.read_only_hint is False
    ]
    assert writers == [GAP_TOOL]
    gap = tools[GAP_TOOL].annotations
    assert gap is not None
    assert (gap.read_only_hint, gap.destructive_hint, gap.idempotent_hint, gap.open_world_hint) == (
        False,
        False,
        False,
        False,
    )
    for name in CONTENT_TOOLS:
        annotations = tools[name].annotations
        assert annotations is not None, name
        assert (
            annotations.read_only_hint,
            annotations.destructive_hint,
            annotations.idempotent_hint,
            annotations.open_world_hint,
        ) == (True, False, True, False), name


async def test_tools_list_is_identical_across_calls(server: FastMCP) -> None:
    async with Client(server) as client:
        first = [tool.model_dump() for tool in await client.list_tools()]
        second = [tool.model_dump() for tool in await client.list_tools()]
    assert first == second


async def test_resource_template_and_instructions(server: FastMCP) -> None:
    async with Client(server) as client:
        templates = await client.list_resource_templates()
        assert client.instructions
    assert "handbook://{pagina}" in [template.uri_template for template in templates]
