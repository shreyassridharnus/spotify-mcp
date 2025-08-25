import asyncio, httpx, json
import spotify.auth as auth

async def main():
    env = auth.load_env()
    token = await auth.get_access_token(env["CLIENT_ID"], env["CLIENT_SECRET"])
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(r.status_code, r.json()["display_name"])

if __name__ == "__main__":
    asyncio.run(main())
