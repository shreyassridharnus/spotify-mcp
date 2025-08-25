
import os
import json
import time
import pytest
import spotify.auth as auth

# Ensure pytest-asyncio is active for async test support
pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_exchange_code_for_token_invalid_secret(monkeypatch):
    # Use a dummy code and intentionally wrong secret
    env = auth.load_env()
    wrong_secret = "WRONG_SECRET"
    # Use a dummy code that will fail
    code = "dummy_code"
    with pytest.raises(Exception) as excinfo:
        await auth.exchange_code_for_token(
            code, env["CLIENT_ID"], wrong_secret, env["REDIRECT_URI"]
        )
    # Should be an httpx.HTTPStatusError with response
    assert hasattr(excinfo.value, 'response')
    resp = excinfo.value.response
    assert resp.status_code == 400 or resp.status_code == 401
    assert resp.text
    return resp

@pytest.mark.asyncio
async def test_get_access_token_refresh(monkeypatch, tmp_path):
    # Setup: Write a tokens.json with expired access token
    env = auth.load_env()
    tokens_path = auth.TOKENS_PATH
    # Backup original tokens.json
    if os.path.exists(tokens_path):
        os.rename(tokens_path, tokens_path + ".bak")
    try:
        # Write expired tokens
        tokens = {
            "access_token": "expired",
            "refresh_token": os.environ.get("SPOTIFY_REFRESH_TOKEN", "dummy_refresh"),
            "expires_at": int(time.time()) - 1,
            "scopes": auth.SCOPES,
        }
        with open(tokens_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f)
        # Patch refresh_access_token to check if called
        called = {}
        async def fake_refresh(tokens, cid, csec):
            called["yes"] = True
            return "new_token"
        monkeypatch.setattr(auth, "refresh_access_token", fake_refresh)
        token = await auth.get_access_token(env["CLIENT_ID"], env["CLIENT_SECRET"])
        assert token == "new_token"
        assert called["yes"]
    finally:
        # Restore original tokens.json
        if os.path.exists(tokens_path + ".bak"):
            os.replace(tokens_path + ".bak", tokens_path)
