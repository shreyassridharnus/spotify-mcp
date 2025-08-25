import os
import json
import time
import base64
from typing import Optional
from urllib.parse import urlencode
import httpx
from spotify.constants import TOKENS_PATH

SCOPES = "user-modify-playback-state user-read-playback-state user-read-currently-playing"

# Environment loading (dotenv optional)
def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    return {
        "CLIENT_ID": os.getenv("SPOTIFY_CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("SPOTIFY_CLIENT_SECRET"),
        "REDIRECT_URI": os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8787/callback"),
        "PORT": int(os.getenv("PORT", "8787")),
    }

def save_tokens(data: dict):
    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_tokens() -> Optional[dict]:
    if not os.path.exists(TOKENS_PATH):
        return None
    with open(TOKENS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def b64_client_creds(client_id, client_secret) -> str:
    raw = f"{client_id}:{client_secret}".encode()
    return base64.b64encode(raw).decode()

def build_login_url(client_id, redirect_uri, scopes=SCOPES):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
    }
    return "https://accounts.spotify.com/authorize?" + urlencode(params)

async def exchange_code_for_token(code, client_id, client_secret, redirect_uri, scopes=SCOPES):
    token_url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {b64_client_creds(client_id, client_secret)}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(token_url, data=data, headers=headers)
        r.raise_for_status()
        tok = r.json()
    expires_at = int(time.time()) + int(tok["expires_in"])
    tokens = {
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token"),
        "expires_at": expires_at,
        "scopes": scopes,
    }
    save_tokens(tokens)
    return tokens

def need_refresh(tokens: dict) -> bool:
    return int(time.time()) > int(tokens["expires_at"]) - 10

async def refresh_access_token(tokens, client_id, client_secret):
    token_url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {b64_client_creds(client_id, client_secret)}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(token_url, data=data, headers=headers)
        r.raise_for_status()
        newtok = r.json()
    tokens["access_token"] = newtok["access_token"]
    tokens["expires_at"] = int(time.time()) + int(newtok["expires_in"])
    if newtok.get("refresh_token"):
        tokens["refresh_token"] = newtok["refresh_token"]
    save_tokens(tokens)
    return tokens["access_token"]

async def get_access_token(client_id, client_secret):
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("Not authorized yet. Visit /login first.")
    if not need_refresh(tokens):
        return tokens["access_token"]
    return await refresh_access_token(tokens, client_id, client_secret)
