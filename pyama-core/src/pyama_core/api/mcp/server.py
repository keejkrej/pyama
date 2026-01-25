"""FastMCP server for PyAMA Core.

This module creates the MCP server instance that exposes pyama-core
functionality as MCP tools.
"""

from mcp.server.fastmcp import FastMCP

# Create the MCP server instance
mcp = FastMCP(
    name="PyAMA Core",
    json_response=True,  # Return JSON responses for better interop
)
