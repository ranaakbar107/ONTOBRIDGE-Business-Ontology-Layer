"""Read-only MCP server exposing the semantic layer as nine tools.

Run it::

    ontobridge --ontology examples/ecommerce/ontology.yaml \\
               --mapping examples/ecommerce/mapping.yaml            # stdio (default)
    ontobridge ... --transport http --port 8000                     # HTTP on /mcp

Paths can also come from ONTOBRIDGE_ONTOLOGY and ONTOBRIDGE_MAPPING.
"""

from __future__ import annotations

import argparse
import functools
import os
import sys
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from ontobridge import __version__
from ontobridge.core.errors import OntoBridgeError
from ontobridge.project import load_project
from ontobridge.semantic import SemanticLayer

TOOL_NAMES = [
    "list_concepts",
    "get_concept",
    "search_terms",
    "get_relationships",
    "find_path",
    "query_entities",
    "get_neighbors",
    "get_metric",
    "check_answerable",
]

INSTRUCTIONS = """\
This server explains the meaning of a business. Start with list_concepts, use
search_terms to turn a business word (e.g. "buyer") into a concept, and
check_answerable before answering a question. get_metric gives the official
definition and value of a metric such as revenue. Every answer includes a
'source' block: cite it. The server is read-only."""


def _safe(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Turn ontobridge errors into clean MCP tool errors the agent can read."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except (OntoBridgeError, ValueError, KeyError) as exc:
            raise ToolError(str(exc)) from None

    return wrapper


def build_server(layer: SemanticLayer, name: str = "ontobridge") -> FastMCP:
    """Create a FastMCP server with the nine read-only tools bound to ``layer``."""
    mcp = FastMCP(name=name, instructions=INSTRUCTIONS)
    read_only = {"readOnlyHint": True, "openWorldHint": False}

    # -- discovery tools -------------------------------------------------------
    @mcp.tool(annotations=read_only)
    @_safe
    def list_concepts() -> dict[str, Any]:
        """List every business concept (entity) with its description, synonyms and
        number of instances, plus the names of all relationships and metrics."""
        return layer.list_concepts()

    @mcp.tool(annotations=read_only)
    @_safe
    def get_concept(
        name: Annotated[
            str, Field(description="Concept name or synonym, e.g. 'Customer' or 'buyer'")
        ],
    ) -> dict[str, Any]:
        """Show one concept: typed properties, key, synonyms, relationships and metrics."""
        return layer.get_concept(name)

    @mcp.tool(annotations=read_only)
    @_safe
    def search_terms(
        term: Annotated[
            str, Field(description="A business word or phrase, e.g. 'buyer' or 'sales'")
        ],
    ) -> dict[str, Any]:
        """Resolve a business word to the concept, relationship or metric it means.
        Returns an empty 'matches' list (and suggestions) when the word is unknown."""
        return layer.search_terms(term)

    # -- graph tools ------------------------------------------------------------
    @mcp.tool(annotations=read_only)
    @_safe
    def get_relationships(
        concept: Annotated[str, Field(description="Concept name or synonym")],
    ) -> dict[str, Any]:
        """List the relationships around a concept with direction and cardinality."""
        return layer.get_relationships(concept)

    @mcp.tool(annotations=read_only)
    @_safe
    def find_path(
        from_concept: Annotated[str, Field(description="Start concept, e.g. 'Customer'")],
        to_concept: Annotated[str, Field(description="End concept, e.g. 'Product'")],
    ) -> dict[str, Any]:
        """Shortest chain of relationships between two concepts,
        e.g. Customer -places-> Order -contains-> Product."""
        return layer.find_path(from_concept, to_concept)

    @mcp.tool(annotations=read_only)
    @_safe
    def query_entities(
        concept: Annotated[str, Field(description="Concept to list, e.g. 'Order'")],
        filters: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    'Property filters. Equality: {"status": "paid"}. Operators: '
                    '{"amount": {"gte": 100}}; ops are eq, ne, gt, gte, lt, lte, in, contains.'
                )
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=100, description="Max results (1-100)")] = 20,
    ) -> dict[str, Any]:
        """Filter instances of a concept. Returns the total count and up to 'limit' rows."""
        return layer.query_entities(concept, filters, limit)

    @mcp.tool(annotations=read_only)
    @_safe
    def get_neighbors(
        node_id: Annotated[str, Field(description="Node id such as 'Customer:C001'")],
        relationship: Annotated[
            str | None, Field(description="Only follow this relationship (optional)")
        ] = None,
        direction: Annotated[
            Literal["out", "in", "both"], Field(description="Edge direction to follow")
        ] = "both",
        limit: Annotated[int, Field(ge=1, le=100, description="Max results (1-100)")] = 20,
    ) -> dict[str, Any]:
        """Instances connected to one node, e.g. the orders a customer placed."""
        return layer.get_neighbors(node_id, relationship, direction, limit)

    # -- semantic tools -----------------------------------------------------------
    @mcp.tool(annotations=read_only)
    @_safe
    def get_metric(
        name: Annotated[str, Field(description="Metric name or synonym, e.g. 'revenue'")],
    ) -> dict[str, Any]:
        """The official business definition of a metric, its formula and its computed value."""
        return layer.get_metric(name)

    @mcp.tool(annotations=read_only)
    @_safe
    def check_answerable(
        question: Annotated[str, Field(description="The user's question in plain language")],
    ) -> dict[str, Any]:
        """Say whether the ontology covers a question, which terms matched and which are
        missing, with a coverage score from 0 to 1. Call this before answering."""
        return layer.check_answerable(question)

    return mcp


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ontobridge", description="Serve a business ontology to AI agents over MCP."
    )
    parser.add_argument(
        "--ontology",
        default=os.environ.get("ONTOBRIDGE_ONTOLOGY"),
        help="Path to the ontology YAML (env: ONTOBRIDGE_ONTOLOGY)",
    )
    parser.add_argument(
        "--mapping",
        default=os.environ.get("ONTOBRIDGE_MAPPING"),
        help="Path to the data mapping YAML (env: ONTOBRIDGE_MAPPING)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("ONTOBRIDGE_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.environ.get("ONTOBRIDGE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ONTOBRIDGE_PORT", 8000)))
    parser.add_argument("--version", action="version", version=f"ontobridge {__version__}")
    args = parser.parse_args(argv)
    if not args.ontology:
        parser.error("--ontology is required (or set ONTOBRIDGE_ONTOLOGY)")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        layer, report = load_project(args.ontology, args.mapping)
    except OntoBridgeError as exc:
        print(f"ontobridge: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    # stdout is the MCP channel in stdio mode, so log to stderr.
    print(
        f"ontobridge {__version__}: loaded '{layer.ontology.name}' "
        f"({report.nodes} nodes, {report.edges} edges)",
        file=sys.stderr,
    )
    server = build_server(layer)
    if args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":  # pragma: no cover
    main()
