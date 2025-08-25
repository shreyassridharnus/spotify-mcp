# spotify/playback.py
"""Playback utilities and argument handling for Spotify Web API."""

from typing import Any, Dict, List, Optional


class PlayArgsError(ValueError):
    """Error raised when invalid playback arguments are provided."""
    pass


def build_play_body(
    *, 
    track_uri: Optional[str] = None, 
    context_uri: Optional[str] = None,
    uris: Optional[List[str]] = None, 
    position_ms: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build request body for Spotify play API.
    
    Spotify accepts either context_uri OR uris (list) OR a single track_uri as [uris].
    """
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
