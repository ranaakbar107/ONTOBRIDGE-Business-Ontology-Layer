"""KAN-18, KAN-22, KAN-23, KAN-24: FastMCP server and its nine tools,
each tested through a real MCP client (in-memory transport)."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from ontobridge.mcp_server import TOOL_NAMES, build_server
from ontobridge.mcp_server.server import parse_args


@pytest.fixture
def server(layer):
    return build_server(layer)


def _schema(tool) -> dict:
    return getattr(tool, "input_schema", None) or tool.inputSchema


async def _call(server, name, args=None) -> dict:
    async with Client(server) as client:
        result = await client.call_tool(name, args or {})
    data = result.structured_content or json.loads(result.content[0].text)
    json.dumps(data)  # outputs are plain JSON
    return data


# -- KAN-18: server skeleton --------------------------------------------------------
async def test_client_connects_and_sees_all_nine_tools(server):
    async with Client(server) as client:
        tools = await client.list_tools()
    assert sorted(t.name for t in tools) == sorted(TOOL_NAMES)
    assert len(tools) == 9
    for tool in tools:
        assert tool.description and len(tool.description) > 20, tool.name
        assert _schema(tool)["type"] == "object"


def test_paths_from_command_line_and_env(monkeypatch):
    args = parse_args(
        ["--ontology", "o.yaml", "--mapping", "m.yaml", "--transport", "http", "--port", "9000"]
    )
    assert (args.ontology, args.mapping, args.transport, args.port) == (
        "o.yaml",
        "m.yaml",
        "http",
        9000,
    )
    monkeypatch.setenv("ONTOBRIDGE_ONTOLOGY", "env.yaml")
    assert parse_args([]).ontology == "env.yaml"
    assert parse_args([]).transport == "stdio"


def test_missing_ontology_argument_exits(monkeypatch):
    monkeypatch.delenv("ONTOBRIDGE_ONTOLOGY", raising=False)
    with pytest.raises(SystemExit):
        parse_args([])


# -- KAN-22: discovery tools ------------------------------------------------------------
async def test_list_concepts(server):
    data = await _call(server, "list_concepts")
    assert {c["name"] for c in data["concepts"]} == {"Customer", "Order", "Product", "Category"}
    assert "revenue" in data["metrics"] and data["source"]["ontology_file"] == "ontology.yaml"


async def test_get_concept(server):
    data = await _call(server, "get_concept", {"name": "buyer"})
    assert data["name"] == "Customer" and data["instances"] == 10
    assert {p["name"] for p in data["properties"]} >= {"id", "name", "email"}
    assert data["relationships"][0]["name"] == "places"


async def test_search_terms(server):
    data = await _call(server, "search_terms", {"term": "buyer"})
    assert data["matches"][0]["target"] == "Customer"
    data = await _call(server, "search_terms", {"term": "custmer"})
    assert data["matches"] == [] and "customer" in data["suggestions"]


# -- KAN-23: graph tools ----------------------------------------------------------------
async def test_get_relationships(server):
    data = await _call(server, "get_relationships", {"concept": "Order"})
    by_name = {r["name"]: r for r in data["relationships"]}
    assert by_name["places"]["direction"] == "incoming"
    assert by_name["contains"]["cardinality"] == "many-to-many"


async def test_find_path(server):
    data = await _call(server, "find_path", {"from_concept": "Customer", "to_concept": "Product"})
    assert data["path"] == ["Customer", "places", "Order", "contains", "Product"]


async def test_query_entities_with_limit(server):
    data = await _call(
        server, "query_entities", {"concept": "Order", "filters": {"status": "paid"}, "limit": 3}
    )
    assert data["count"] == 20 and data["returned"] == 3 and data["truncated"]


async def test_get_neighbors_with_limit(server):
    data = await _call(
        server, "get_neighbors", {"node_id": "Customer:C001", "relationship": "places", "limit": 2}
    )
    assert data["count"] == 4 and data["returned"] == 2


async def test_limit_is_validated_by_schema(server):
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("query_entities", {"concept": "Order", "limit": 1000})


# -- KAN-24: semantic tools -------------------------------------------------------------
async def test_get_metric(server):
    data = await _call(server, "get_metric", {"name": "revenue"})
    assert data["formula"] == "sum of Order.amount where status = paid"
    assert data["value"] > 0


async def test_check_answerable(server):
    data = await _call(server, "check_answerable", {"question": "How much ad spend?"})
    assert data["answerable"] is False and data["missing_terms"] == ["ad", "spend"]
    data = await _call(server, "check_answerable", {"question": "What is revenue?"})
    assert data["answerable"] is True


# -- errors -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("get_concept", {"name": "Unicorn"}, "Unknown concept 'Unicorn'"),
        ("get_metric", {"name": "profit"}, "Unknown metric 'profit'"),
        ("get_neighbors", {"node_id": "nope"}, "Node 'nope' not found"),
        ("query_entities", {"concept": "Order", "filters": {"x": 1}}, "has no property 'x'"),
    ],
)
async def test_errors_are_clear_tool_errors(server, tool, args, message):
    async with Client(server) as client:
        with pytest.raises(ToolError, match=message):
            await client.call_tool(tool, args)
