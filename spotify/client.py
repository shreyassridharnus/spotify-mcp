# spotify/client.py
"""HTTP client and API utilities for Spotify Web API."""

from typing import Any, Dict

import httpx

from .constants import SPOTIFY_API
from . import auth as sa


# Global configuration - will be set by server initialization
CLIENT_ID: str = ""
CLIENT_SECRET: str = ""


def initialize_client(client_id: str, client_secret: str) -> None:
    """Initialize the client with credentials."""
    global CLIENT_ID, CLIENT_SECRET
    CLIENT_ID = client_id
    CLIENT_SECRET = client_secret


async def bearer_headers() -> Dict[str, str]:
    """Get authorization headers with current access token."""
    token = await sa.get_access_token(CLIENT_ID, CLIENT_SECRET)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def spotify_request(
    method: str, 
    path: str, 
    *, 
    params: dict | None = None, 
    json_body: Any | None = None
) -> httpx.Response:
    """Make an authenticated request to the Spotify API."""
    headers = await bearer_headers()
    url = f"{SPOTIFY_API}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        r = await client.request(method, url, headers=headers, params=params, json=json_body)
        return r
