from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, PlainTextResponse
import spotify.auth as auth

env = auth.load_env()
CLIENT_ID = env["CLIENT_ID"]
CLIENT_SECRET = env["CLIENT_SECRET"]
REDIRECT_URI = env["REDIRECT_URI"]
PORT = env["PORT"]

app = FastAPI()

@app.get("/login")
def login():
    url = auth.build_login_url(CLIENT_ID, REDIRECT_URI)
    return RedirectResponse(url)

@app.get("/callback")
async def callback(req: Request):
    code = req.query_params.get("code")
    if not code:
        return PlainTextResponse("Missing 'code' param", status_code=400)
    await auth.exchange_code_for_token(code, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    return PlainTextResponse("Spotify authorization complete. You can close this tab.")

# Example: how to get a valid access token (refreshes if needed)
# async def get_token():
#     return await auth.get_access_token(CLIENT_ID, CLIENT_SECRET)
