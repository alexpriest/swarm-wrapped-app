"""
Swarm Wrapped - A web app to generate Spotify Wrapped-style reports from Foursquare Swarm data.
"""

import os
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from analyze import analyze_checkins

app = FastAPI(title="Swarm Wrapped")

# Session middleware for storing OAuth tokens
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-production")
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Foursquare OAuth configuration
FOURSQUARE_CLIENT_ID = os.environ.get("FOURSQUARE_CLIENT_ID")
FOURSQUARE_CLIENT_SECRET = os.environ.get("FOURSQUARE_CLIENT_SECRET")
FOURSQUARE_REDIRECT_URI = os.environ.get("FOURSQUARE_REDIRECT_URI", "http://localhost:8000/callback")

# Foursquare API endpoints
FOURSQUARE_AUTH_URL = "https://foursquare.com/oauth2/authenticate"
FOURSQUARE_TOKEN_URL = "https://foursquare.com/oauth2/access_token"
FOURSQUARE_API_BASE = "https://api.foursquare.com/v2"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page with connect button."""
    token = request.session.get("access_token")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": token is not None
    })


@app.get("/login")
async def login():
    """Redirect to Foursquare OAuth."""
    if not FOURSQUARE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Foursquare client ID not configured")

    auth_url = (
        f"{FOURSQUARE_AUTH_URL}"
        f"?client_id={FOURSQUARE_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={FOURSQUARE_REDIRECT_URI}"
    )
    return RedirectResponse(url=auth_url)


@app.get("/callback")
async def callback(request: Request, code: str = None, error: str = None):
    """Handle OAuth callback from Foursquare."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FOURSQUARE_TOKEN_URL,
            params={
                "client_id": FOURSQUARE_CLIENT_ID,
                "client_secret": FOURSQUARE_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": FOURSQUARE_REDIRECT_URI,
                "code": code
            }
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        data = response.json()
        access_token = data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in response")

        # Store token in session
        request.session["access_token"] = access_token

    return RedirectResponse(url="/generate")


@app.get("/generate", response_class=HTMLResponse)
async def generate(request: Request):
    """Fetch check-ins and generate the wrapped report."""
    token = request.session.get("access_token")

    if not token:
        return RedirectResponse(url="/login")

    # Show loading page that will trigger the actual generation
    return templates.TemplateResponse("loading.html", {"request": request})


@app.get("/api/generate")
async def api_generate(request: Request):
    """API endpoint to fetch and analyze check-ins."""
    token = request.session.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Fetch check-ins from Foursquare
    checkins = await fetch_all_checkins(token, year=2025)

    if not checkins:
        return {"error": "No check-ins found for 2025"}

    # Analyze the check-ins
    stats = analyze_checkins(checkins)

    return stats


@app.get("/wrapped", response_class=HTMLResponse)
async def wrapped(request: Request, exclude_sensitive: bool = False):
    """Display the generated wrapped report."""
    token = request.session.get("access_token")

    if not token:
        return RedirectResponse(url="/login")

    # Fetch user profile and check-ins
    user_profile = await fetch_user_profile(token)
    checkins_2025 = await fetch_all_checkins(token, year=2025)

    if not checkins_2025:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "No check-ins found for 2025"
        })

    stats = analyze_checkins(checkins_2025, exclude_sensitive=exclude_sensitive)

    # Get lifetime checkin count from user profile (fast - no extra API calls)
    lifetime_checkins = None
    if user_profile:
        lifetime_checkins = user_profile.get("checkins", {}).get("count")

    # Get username for display
    username = None
    if user_profile:
        first_name = user_profile.get("firstName", "")
        last_name = user_profile.get("lastName", "")
        username = f"{first_name} {last_name}".strip() or user_profile.get("handle", "")

    return templates.TemplateResponse("wrapped.html", {
        "request": request,
        "stats": stats,
        "lifetime_checkins": lifetime_checkins,
        "exclude_sensitive": exclude_sensitive,
        "username": username
    })


@app.get("/logout")
async def logout(request: Request):
    """Clear session and logout."""
    request.session.clear()
    return RedirectResponse(url="/")


async def fetch_user_profile(token: str) -> dict:
    """Fetch user profile from Foursquare API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{FOURSQUARE_API_BASE}/users/self",
            params={
                "oauth_token": token,
                "v": "20231201"
            }
        )

        if response.status_code != 200:
            return {}

        data = response.json()
        return data.get("response", {}).get("user", {})


async def fetch_all_checkins(token: str, year: int = 2025) -> list:
    """Fetch all check-ins for a given year from Foursquare API."""
    checkins = []
    offset = 0
    limit = 250  # Max allowed by Foursquare API

    # Date range for the year
    start_timestamp = int(datetime(year, 1, 1).timestamp())
    end_timestamp = int(datetime(year, 12, 31, 23, 59, 59).timestamp())

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"{FOURSQUARE_API_BASE}/users/self/checkins",
                params={
                    "oauth_token": token,
                    "v": "20231201",  # API version
                    "limit": limit,
                    "offset": offset,
                    "afterTimestamp": start_timestamp,
                    "beforeTimestamp": end_timestamp,
                    "sort": "newestfirst"
                }
            )

            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("response", {}).get("checkins", {}).get("items", [])

            if not items:
                break

            checkins.extend(items)
            offset += limit

            # Safety limit
            if offset > 5000:
                break

    return checkins


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
