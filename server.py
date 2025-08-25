# server.py
import json
import time
from typing import Any, Dict, List, Optional, NamedTuple

import httpx
from mcp.server.fastmcp import FastMCP


from spotify.constants import SPOTIFY_API
import spotify.auth as sa

mcp = FastMCP("spotify-mcp")

ENV = sa.load_env()
CLIENT_ID = ENV["CLIENT_ID"]
CLIENT_SECRET = ENV["CLIENT_SECRET"]



# ---------- low-level HTTP helper using your refresher ----------
async def _bearer_headers() -> Dict[str, str]:
    token = await sa.get_access_token(CLIENT_ID, CLIENT_SECRET)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

async def _spotify_req(method: str, path: str, *, params: dict | None = None, json_body: Any | None = None) -> httpx.Response:
    headers = await _bearer_headers()
    url = f"{SPOTIFY_API}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        r = await client.request(method, url, headers=headers, params=params, json=json_body)
        return r

# ---------- device data structures and cache ----------
class DeviceInfo(NamedTuple):
    id: str
    name: str
    is_active: bool
    volume_percent: Optional[int]
    type: str

class DevicesCache:
    def __init__(self, ttl_seconds: int = 10):
        self.ttl_seconds = ttl_seconds
        self._devices: List[DeviceInfo] = []
        self._last_fetch: float = 0
    
    def is_expired(self) -> bool:
        return time.time() - self._last_fetch > self.ttl_seconds
    
    def update(self, devices: List[DeviceInfo]) -> None:
        self._devices = devices
        self._last_fetch = time.time()
    
    def get_devices(self) -> List[DeviceInfo]:
        return self._devices.copy()

_devices_cache = DevicesCache()

# ---------- optimized device fetching ----------
async def _fetch_devices_data() -> List[DeviceInfo]:
    """
    Fetch devices from Spotify API and return structured data.
    Includes caching to avoid redundant API calls.
    """
    if not _devices_cache.is_expired():
        return _devices_cache.get_devices()
    
    r = await _spotify_req("GET", "/me/player/devices")
    if r.status_code != 200:
        raise RuntimeError(f"devices API failed: {r.status_code} {r.text}")
    
    raw_devices = r.json().get("devices", []) or []
    devices = [
        DeviceInfo(
            id=d.get("id", ""),
            name=d.get("name", "Unknown"),
            is_active=bool(d.get("is_active", False)),
            volume_percent=d.get("volume_percent"),
            type=d.get("type", "Unknown")
        )
        for d in raw_devices
        if d.get("id")  # Only include devices with valid IDs
    ]
    
    _devices_cache.update(devices)
    return devices

# ---------- helpers ----------
async def get_active_device_id() -> Optional[str]:
    """
    Get the ID of the active device, or the first available device if none is active.
    Uses cached device data to minimize API calls.
    """
    try:
        devices = await _fetch_devices_data()
        if not devices:
            return None
        
        # Find active device first
        active_device = next((d for d in devices if d.is_active), None)
        if active_device:
            return active_device.id
        
        # Fall back to first device if no active device
        return devices[0].id
    except RuntimeError:
        # Re-raise with more context for device-specific failures
        raise

async def invalidate_devices_cache() -> None:
    """Force refresh of devices cache on next access."""
    _devices_cache._last_fetch = 0

async def get_device_by_id(device_id: str) -> Optional[DeviceInfo]:
    """Get specific device info by ID."""
    devices = await _fetch_devices_data()
    return next((d for d in devices if d.id == device_id), None)

class PlayArgsError(ValueError): ...

def build_play_body(
    *, track_uri: Optional[str], context_uri: Optional[str],
    uris: Optional[List[str]], position_ms: Optional[int]
) -> Dict[str, Any]:
    """Spotify accepts either context_uri OR uris (list) OR a single track_uri as [uris]."""
    # exactly one of (context_uri, uris, track_uri) may be provided
    provided = sum(x is not None for x in (context_uri, uris, track_uri))
    if provided == 0:
        # legal: empty body => resume on current context
        body = {}
    elif provided > 1:
        raise PlayArgsError("Provide only one of: context_uri, uris, track_uri.")
    else:
        if context_uri:
            body = {"context_uri": context_uri}
        elif uris:
            body = {"uris": uris}
        else:
            body = {"uris": [track_uri]}  # single track

    if position_ms is not None:
        if position_ms < 0:
            raise PlayArgsError("position_ms must be >= 0")
        body["position_ms"] = int(position_ms)
    return body

async def _spotify_search_tracks(q: str, limit: int = 5):
    r = await _spotify_req("GET", "/search", params={"q": q, "type": "track", "limit": limit}, json_body=None)
    if r.status_code != 200:
        raise RuntimeError(f"search failed: {r.status_code} {r.text}")
    items = (r.json().get("tracks") or {}).get("items", []) or []
    # return small, readable tuples
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

# ---------- resources ----------
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
        device_list = await _fetch_devices_data()
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
    "Slim view of GET /me/player."
    r = await _spotify_req("GET", "/me/player")
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

# ---------- tools ----------
@mcp.tool()
async def spotify_pause() -> str:
    """
    Pause playback on the active device.
    Returns human-readable status; handles common Spotify errors explicitly.
    """
    device_id = await get_active_device_id()
    params = {"device_id": device_id} if device_id else None
    r = await _spotify_req("PUT", "/me/player/pause", params=params)
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

    r = await _spotify_req("PUT", "/me/player/play", params=params, json_body=body if body else None)

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
    results = await _spotify_search_tracks(q=q, limit=limit)
    return json.dumps(results, indent=2)

# quick ping tool for sanity
@mcp.tool()
def ping() -> str:
    return "pong"

if __name__ == "__main__":
    mcp.run()
