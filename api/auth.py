"""/api/auth/* Handlers."""

import os
import secrets
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer

from database.cookies import clear_auth_cookies, get_current_user, set_auth_cookies
from database.models import StaffMember
from database.staff import get_staff, has_staff_admin_perms

load_dotenv()
router = APIRouter(prefix="/auth")

CLIENT_ID: str = os.environ["DISCORD_CLIENT_ID"]
CLIENT_SECRET: str = os.environ["DISCORD_CLIENT_SECRET"]
REDIRECT_URI: str = os.environ["REDIRECT_URI"] + "/api/auth/discord/callback"
serializer = URLSafeSerializer(os.environ["SECRET_KEY"])


@router.get("/discord/login")
def discord_login() -> RedirectResponse:
    """Redirect the user to the Discord OAuth2 authorization page.

    Generates a secure state token and saves it in an HTTP-only cookie.
    Constructs the authorization URL and redirects the user.

    Returns:
        RedirectResponse: A redirect response to Discord with the state cookie set.
    """
    state = secrets.token_urlsafe(16)
    signed_state = serializer.dumps(state)
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    url = "https://discord.com/oauth2/authorize?" + httpx.QueryParams(params).__str__()
    resp = RedirectResponse(url)
    resp.set_cookie("oauth_state", signed_state, httponly=True, max_age=600, samesite="lax")
    return resp


@router.get("/discord/callback")
async def discord_callback(request: Request, code: str, state: str) -> RedirectResponse:
    """Process the OAuth2 callback from Discord.

    Validates the state parameter against the stored cookie. Exchanges the authorization code for access tokens, fetches user details from Discord, and verifies staff authorization before redirecting to the dashboard.

    Args:
        request: The incoming HTTP request.
        code: The authorization code provided by Discord.
        state: The state parameter provided by Discord.

    Returns:
        RedirectResponse: A redirect to the dashboard with authentication cookies set.

    Raises:
        HTTPException: 400 Bad Request if the state cookie is missing, invalid, or mismatched.
        HTTPException: 403 Forbidden if the user is not a registered staff member.
    """
    cookie_state: str | None = request.cookies.get("oauth_state")
    if not cookie_state:
        raise HTTPException(400, "Missing state cookie")
    try:
        expected_state = serializer.loads(cookie_state)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Bad state")
    if state != expected_state:
        raise HTTPException(400, "State mismatch")

    async with httpx.AsyncClient() as client:
        token_resp: httpx.Response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_resp.raise_for_status()
        tokens: dict[str, Any] = token_resp.json()

        user_resp: httpx.Response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_resp.raise_for_status()
        discord_user: dict[str, Any] = user_resp.json()

    user: StaffMember | None = await get_staff(discord_id=discord_user["id"])
    if user is None:
        raise HTTPException(403, "Not allowed to access.")

    resp = RedirectResponse("https://www.hes.systems/staffpanel")
    set_auth_cookies(resp, tokens, user)
    resp.delete_cookie("oauth_state")
    return resp


@dataclass
class AuthResponse:
    """Holds authentication data for a user.

    Attributes:
        discord_id: The unique Discord identification string.
        name: The display name of the user.
        role: The permission role of the user ('admin' or 'user').
    """

    discord_id: str
    name: str
    role: Literal["admin", "user"]


@router.get("/me")
async def check_if_authed(user: Annotated[StaffMember, Depends(get_current_user)]) -> AuthResponse:
    """Retrieves the authentication status of the current user.

    Args:
        user: The database record for the authenticated user.

    Returns:
        AuthResponse: The user details and the assigned access role.
    """
    return AuthResponse(discord_id=str(user.discord_id), name=user.name, role="admin" if await has_staff_admin_perms(staff_id=user.staff_id) else "user")


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    """Log the current user out by clearing authentication cookies.

    Args:
        response: The outgoing HTTP response object.
    """
    clear_auth_cookies(response)
