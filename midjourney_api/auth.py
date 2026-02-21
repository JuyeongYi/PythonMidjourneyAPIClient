"""Authentication module for Midjourney API.

Handles Firebase Auth token management: login via Playwright,
token refresh via Firebase REST API, and JWT parsing.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key

from midjourney_api.const import (
    FIREBASE_TOKEN_URL,
    ID_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
)
from midjourney_api.exceptions import AuthenticationError


class MidjourneyAuth:
    """Manages authentication state and token lifecycle.

    Usage:
        auth = MidjourneyAuth()        # loads refresh token from .env
        auth.ensure_valid_token()       # refreshes ID token if needed
        headers = auth.get_headers()    # returns auth headers for requests
    """

    def __init__(self, refresh_token: str | None = None, env_path: str = ".env"):
        self._env_path = Path(env_path)
        load_dotenv(self._env_path)

        self._refresh_token = refresh_token or os.getenv("MJ_REFRESH_TOKEN", "")
        self._id_token: str = ""
        self._token_expiry: float = 0
        self._user_id: str = ""

        if self._refresh_token and self._refresh_token != "your_refresh_token_here":  # nosec B105
            self._do_refresh()

    @property
    def user_id(self) -> str:
        if not self._user_id:
            raise AuthenticationError("Not authenticated. Run login() or set MJ_REFRESH_TOKEN.")
        return self._user_id

    @property
    def id_token(self) -> str:
        self.ensure_valid_token()
        return self._id_token

    def ensure_valid_token(self) -> None:
        """Refresh the ID token if it's expired or about to expire (within 60s)."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token. Run login() or set MJ_REFRESH_TOKEN in .env")
        if time.time() >= self._token_expiry - 60:
            self._do_refresh()

    def _do_refresh(self) -> None:
        """Exchange refresh token for a new ID token via Firebase REST API."""
        try:
            resp = httpx.post(
                FIREBASE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise AuthenticationError(
                    "Session expired or revoked (often caused by logging in from a new device). "
                    "Run `midjourney login --force` to re-authenticate."
                ) from e
            raise AuthenticationError(f"Token refresh failed: {e}") from e
        except httpx.HTTPError as e:
            raise AuthenticationError(f"Token refresh failed: {e}") from e

        data = resp.json()
        self._id_token = data["id_token"]

        new_refresh_token = data.get("refresh_token", self._refresh_token)
        if new_refresh_token != self._refresh_token:
            # Firebase rotated the refresh token — persist it so other sessions
            # (e.g. on a different PC) can use the latest token.
            self._refresh_token = new_refresh_token
            if self._env_path.exists():
                set_key(str(self._env_path), "MJ_REFRESH_TOKEN", new_refresh_token)

        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in

        self._user_id = self._parse_user_id(self._id_token)

    def _parse_user_id(self, id_token: str) -> str:
        """Extract midjourney_id from the JWT payload."""
        try:
            payload_b64 = id_token.split(".")[1]
            # Fix padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            mid = payload.get("midjourney_id", "")
            if not mid:
                raise AuthenticationError("midjourney_id not found in JWT payload")
            return str(mid)
        except (IndexError, json.JSONDecodeError, KeyError) as e:
            raise AuthenticationError(f"Failed to parse JWT: {e}") from e

    def cookie_header(self) -> str:
        """Return the Cookie header string with both ID and refresh tokens."""
        self.ensure_valid_token()
        return (
            f"{ID_COOKIE_NAME}={self._id_token}; "
            f"{REFRESH_COOKIE_NAME}={self._refresh_token}"
        )

    def login(self, force: bool = False) -> None:
        """Open a browser for Google OAuth login and extract the refresh token.

        Args:
            force: If True, clear the cached browser session before opening
                   the browser. Use this to switch accounts.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise AuthenticationError(
                "Playwright is required for login. "
                "Install with: pip install playwright && playwright install chromium"
            )

        user_data_path = Path.home() / ".midjourney_browser"
        if force and user_data_path.exists():
            import shutil
            shutil.rmtree(user_data_path)
            print("Cleared browser session for fresh login.")

        print("Opening browser for Midjourney login...")
        print("Please sign in with your Google account.")

        with sync_playwright() as p:
            user_data = str(user_data_path)
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation", "--no-sandbox"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.midjourney.com/")

            # Wait for user to complete login — poll for the refresh token cookie
            refresh_token = ""  # nosec B105
            print("Waiting for login to complete...")
            while not refresh_token:
                page.wait_for_timeout(2000)
                cookies = context.cookies("https://www.midjourney.com")
                for cookie in cookies:
                    if cookie["name"] == REFRESH_COOKIE_NAME:
                        refresh_token = cookie["value"]
                        break

            context.close()

        self._refresh_token = refresh_token
        self._do_refresh()

        # Save to .env
        if not self._env_path.exists():
            self._env_path.write_text("")
        set_key(str(self._env_path), "MJ_REFRESH_TOKEN", refresh_token)
        print("Login successful!")
        print(f"Refresh token saved to {self._env_path}")
