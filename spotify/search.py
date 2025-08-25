# spotify/search.py
"""Search functionality for Spotify Web API."""

from typing import Dict, List

from .client import spotify_request


async def search_tracks(q: str, limit: int = 5) -> List[Dict]:
    """
    Search for tracks on Spotify.
    
    Returns a list of track dictionaries with uri, name, artist, album, and duration.
    """
    r = await spotify_request("GET", "/search", params={"q": q, "type": "track", "limit": limit})
    if r.status_code != 200:
        raise RuntimeError(f"search failed: {r.status_code} {r.text}")
    
    items = (r.json().get("tracks") or {}).get("items", []) or []
    
    # return small, readable dictionaries
    return [
        {
            "uri": it["uri"],
            "name": it["name"],
            "artist": ", ".join(a["name"] for a in it.get("artists", [])),
            "album": (it.get("album") or {}).get("name"),
            "duration_ms": it.get("duration_ms"),
        }
        for it in items
    ]
