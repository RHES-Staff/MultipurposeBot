"""Cookies Management for API."""

import os
from typing import Any

import httpx
from aiosqlite import Row
from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeSerializer

from .staff import get_staff

load_dotenv()
CLIENT_ID: str = os.environ["DISCORD_CLIENT_ID"]
CLIENT_SECRET: str = os.environ["DISCORD_CLIENT_SECRET"]
serializer = URLSafeSerializer(os.environ["SECRET_KEY"])

ACCESS_COOKIE = "access_cookie"
SESSION_COOKIE = "session_cookie"
REFRESH_COOKIE = "refresh_cookie"

REFRESH_MAX_AGE: int = 60 * 60 * 24 * 30  # 30 days, Discord refresh tokens don't expose a ttl


def create_session_cookie(staff: Row) -> str:
    """Creates a serialized session cookie payload from staff data.

    Args:
        staff (Row): Database row containing staff details.

    Returns:
        str: Serialized JSON payload containing staff ID, Discord ID, and name.
    """
    return serializer.dumps({"discord_id": staff["discord_id"], "staff_id": staff["staff_id"], "name": staff["name"]})


def set_auth_cookies(resp: Response, tokens: dict, staff: Row) -> None:
    """Sets secure authentication cookies on the response object.

    Args:
        resp (Response): The HTTP response object.
        tokens (dict): Dictionary containing access and refresh tokens.
        staff (Row): Database row containing staff details.
    """
    access_max_age: int = tokens.get("expires_in", 3600)

    resp.set_cookie(ACCESS_COOKIE, tokens["access_token"], max_age=access_max_age, httponly=True, secure=True, samesite="lax", path="/")
    resp.set_cookie(REFRESH_COOKIE, tokens["refresh_token"], max_age=REFRESH_MAX_AGE, httponly=True, secure=True, samesite="lax", path="/")
    resp.set_cookie(SESSION_COOKIE, create_session_cookie(staff), max_age=REFRESH_MAX_AGE, httponly=True, secure=True, samesite="lax", path="/")


def clear_auth_cookies(resp: Response) -> None:
    """Deletes all authentication cookies from the response object.

    Args:
        resp (Response): The HTTP response object.
    """
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path="/")
    resp.delete_cookie(SESSION_COOKIE, path="/")


async def refresh_access_token(refresh_token: str) -> dict:
    """Requests a new access token from the Discord OAuth2 API.

    Args:
        refresh_token (str): Valid Discord refresh token.

    Returns:
        dict: API response containing new tokens and expiration time.

    Raises:
        httpx.HTTPStatusError: If the Discord API request fails.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_current_user(request: Request, response: Response) -> Row:
    """Validates the session cookie and gets the user record.

    Args:
        request (Request): Incoming HTTP request object.
        response (Response): Outgoing HTTP response object.

    Returns:
        Row: Database row of the authenticated staff member.

    Raises:
        HTTPException: 401 if cookie is missing or invalid.
        HTTPException: 403 if staff member record does not exist.
    """
    session_cookie: str | None = request.cookies.get("session_cookie")
    if not session_cookie:
        raise HTTPException(401, "Not authenticated")
    try:
        data: dict[str, Any] = serializer.loads(session_cookie, max_age=REFRESH_MAX_AGE)
    except Exception:  # noqa: BLE001
        clear_auth_cookies(response)
        raise HTTPException(401, "Session expired")

    user: Row | None = await get_staff(staff_id=data["staff_id"])
    if user is None:
        raise HTTPException(403, "Not allowed to access.")
    return user
