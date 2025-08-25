# spotify/resources.py
"""MCP resources for Spotify data."""

import json

from mcp.server.fastmcp import FastMCP

from . import auth as sa
from .client import spotify_request
from .devices import fetch_devices_data


def register_resources(mcp: FastMCP) -> None:
    """Register all Spotify MCP resources."""
    
    @mcp.resource("spotify://auth/status")
    def auth_status() -> str:
        """
        Shows whether tokens.json is present and when it expires.
        (Use spotify_begin_login in your setup script/flow to obtain tokens first.)
        """
        toks = sa.load_tokens()
        if not toks:
            return "missing"
        return json.dumps(
            {
                "status": "authorized",
                "scopes": toks.get("scopes"),
                "expires_at": toks.get("expires_at"),
            },
            indent=2,
        )

    @mcp.resource("spotify://devices")
    async def devices() -> str:
        """
        List available playback devices (id, name, active, volume).
        Uses cached device data for better performance.
        """
        try:
            device_list = await fetch_devices_data()
            out = [
                {
                    "id": d.id,
                    "name": d.name,
                    "is_active": d.is_active,
                    "volume_percent": d.volume_percent,
                    "type": d.type,
                }
                for d in device_list
            ]
            return json.dumps(out, indent=2)
        except RuntimeError as e:
            return f"error: {str(e)}"

    @mcp.resource("spotify://now-playing")
    async def now_playing() -> str:
        """Slim view of GET /me/player."""
        r = await spotify_request("GET", "/me/player")
        if r.status_code == 204:
            return "No content (nothing playing)."
        if r.status_code != 200:
            return f"error: {r.status_code} {r.text}"
        
        data = r.json() or {}
        item = data.get("item") or {}
        slim = {
            "is_playing": data.get("is_playing"),
            "device": (data.get("device") or {}).get("name"),
            "progress_ms": data.get("progress_ms"),
            "track": {
                "name": item.get("name"),
                "uri": item.get("uri"),
                "artists": [a["name"] for a in (item.get("artists") or [])],
                "album": (item.get("album") or {}).get("name"),
                "duration_ms": item.get("duration_ms"),
            } if item else None,
        }
        return json.dumps(slim, indent=2)
