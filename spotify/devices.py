# spotify/devices.py
"""Device management and caching for Spotify devices."""

import time
from typing import List, NamedTuple, Optional

from .client import spotify_request


class DeviceInfo(NamedTuple):
    """Information about a Spotify playback device."""
    id: str
    name: str
    is_active: bool
    volume_percent: Optional[int]
    type: str


class DevicesCache:
    """Cache for Spotify devices to minimize API calls."""
    
    def __init__(self, ttl_seconds: int = 10):
        self.ttl_seconds = ttl_seconds
        self._devices: List[DeviceInfo] = []
        self._last_fetch: float = 0
    
    def is_expired(self) -> bool:
        """Check if the cache has expired."""
        return time.time() - self._last_fetch > self.ttl_seconds
    
    def update(self, devices: List[DeviceInfo]) -> None:
        """Update the cache with new device data."""
        self._devices = devices
        self._last_fetch = time.time()
    
    def get_devices(self) -> List[DeviceInfo]:
        """Get a copy of cached devices."""
        return self._devices.copy()


# Global cache instance
_devices_cache = DevicesCache()


async def fetch_devices_data() -> List[DeviceInfo]:
    """
    Fetch devices from Spotify API and return structured data.
    Includes caching to avoid redundant API calls.
    """
    if not _devices_cache.is_expired():
        return _devices_cache.get_devices()
    
    r = await spotify_request("GET", "/me/player/devices")
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


async def get_active_device_id() -> Optional[str]:
    """
    Get the ID of the active device, or the first available device if none is active.
    Uses cached device data to minimize API calls.
    """
    try:
        devices = await fetch_devices_data()
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
    devices = await fetch_devices_data()
    return next((d for d in devices if d.id == device_id), None)
