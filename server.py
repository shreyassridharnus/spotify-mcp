# server.py
"""Spotify MCP Server - main entry point."""

from mcp.server.fastmcp import FastMCP

import spotify.auth as sa
from spotify.client import initialize_client
from spotify.resources import register_resources
from spotify.tools import register_tools


def create_server() -> FastMCP:
    """Create and configure the Spotify MCP server."""
    # Initialize FastMCP server
    mcp = FastMCP("spotify-mcp")
    
    # Load environment and initialize client
    env = sa.load_env()
    client_id = env["CLIENT_ID"]
    client_secret = env["CLIENT_SECRET"]
    initialize_client(client_id, client_secret)
    
    # Register all resources and tools
    register_resources(mcp)
    register_tools(mcp)
    
    return mcp

mcp = create_server()
