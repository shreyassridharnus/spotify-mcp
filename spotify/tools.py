# spotify/tools.py
"""MCP tools for Spotify playback control."""

import json
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from .client import spotify_request
from .devices import get_active_device_id
from .playback import build_play_body, PlayArgsError
from .search import search_tracks


def register_tools(mcp: FastMCP) -> None:
    """Register all Spotify MCP tools."""

    @mcp.tool()
    async def spotify_pause() -> str:
        """
        Pause playback on the active device.
        Returns human-readable status; handles common Spotify errors explicitly.
        """
        device_id = await get_active_device_id()
        params = {"device_id": device_id} if device_id else None
        r = await spotify_request("PUT", "/me/player/pause", params=params)
        print(f"spotify_pause: {r.status_code} {r.text}")

        # Success: Spotify returns 204 No Content
        if r.status_code in [204, 200]:
            return "Paused."

        # Common failure modes, translated:
        if r.status_code == 404 and "NO_ACTIVE_DEVICE" in r.text:
            return "No active device. Open Spotify on any device and try again."
        if r.status_code == 403 and "PREMIUM_REQUIRED" in r.text:
            return "Playback control requires Spotify Premium."
        if r.status_code == 401:
            return "Unauthorized (token likely expired or missing). Re-run login and try again."

        return f"Pause failed: {r.status_code} {r.text}"

    @mcp.tool()
    async def spotify_play(
        track_uri: Optional[str] = None,
        context_uri: Optional[str] = None,
        uris: Optional[List[str]] = None,
        position_ms: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> str:
        """
        Start/resume playback.
        Use exactly one of: track_uri, context_uri, uris[]. If none, resumes current context.
        Optionally pass position_ms, and/or a device_id (falls back to active device).
        """
        try:
            body = build_play_body(
                track_uri=track_uri,
                context_uri=context_uri,
                uris=uris,
                position_ms=position_ms,
            )
        except PlayArgsError as e:
            return f"Invalid arguments: {e}"

        # choose device
        dev = device_id or await get_active_device_id()
        params = {"device_id": dev} if dev else None

        r = await spotify_request("PUT", "/me/player/play", params=params, json_body=body if body else None)

        if r.status_code in (200, 204):
            # 204 is common success
            target = dev or "(default/active device)"
            what = (
                context_uri or
                (uris[0] if uris else None) or
                track_uri or
                "current context"
            )
            return f"Playing {what} on {target}."
        if r.status_code == 403 and "PREMIUM_REQUIRED" in r.text:
            return "Playback control requires Spotify Premium."
        if r.status_code == 404 and "NO_ACTIVE_DEVICE" in r.text:
            return "No active device. Open Spotify on any device or pass a device_id, then try again."
        if r.status_code == 401:
            return "Unauthorized. Re-run login (token missing/expired)."
        return f"Play failed: {r.status_code} {r.text}"

    @mcp.tool()
    async def spotify_search_tracks(q: str, limit: int = 5) -> str:
        """
        Search tracks by text; returns small JSON list with 'uri', 'name', 'artist'.
        Use first result with spotify_play(track_uri=...).
        """
        results = await search_tracks(q=q, limit=limit)
        return json.dumps(results, indent=2)

    @mcp.tool()
    def ping() -> str:
        """Quick ping tool for sanity checks."""
        return "pong"
