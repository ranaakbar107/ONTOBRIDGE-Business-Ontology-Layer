"""FastMCP server exposing the semantic layer to AI agents."""

from ontobridge.mcp_server.server import TOOL_NAMES, build_server, main

__all__ = ["TOOL_NAMES", "build_server", "main"]
