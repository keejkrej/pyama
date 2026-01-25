"""MCP integration for PyAMA Core API.

This module provides MCP (Model Context Protocol) tools for interacting with
pyama-core functionality via Claude or other MCP clients.
"""

from pyama_core.api.mcp.server import mcp
from pyama_core.api.mcp import tools  # noqa: F401 - Import to register tools

__all__ = ["mcp"]
