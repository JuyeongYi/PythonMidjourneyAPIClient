"""Midjourney API 인증 모듈.

Firebase Auth 토큰 관리를 처리합니다: Playwright를 통한 로그인,
Firebase REST API를 통한 토큰 갱신, JWT 파싱.
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
    """인증 상태 및 토큰 수명 주기를 관리합니다.

    사용법:
        auth = MidjourneyAuth()        # .env에서 refresh token 로드
        auth.ensure_valid_token()       # 필요 시 ID 토큰 갱신
        headers = auth.get_headers()    # 요청용 인증 헤더 반환
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
        """ID 토큰이 만료됐거나 곧 만료될 경우(60초 이내) 갱신합니다."""
        if not self._refresh_token:
            raise AuthenticationError("No refresh token. Run login() or set MJ_REFRESH_TOKEN in .env")
        if time.time() >= self._token_expiry - 60:
            self._do_refresh()

    def _do_refresh(self) -> None:
        """Firebase REST API를 통해 refresh token으로 새 ID 토큰을 교환합니다."""
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
            # Firebase가 refresh token을 교체한 경우 — 다른 세션에서도
            # 최신 토큰을 사용할 수 있도록 저장합니다.
            self._refresh_token = new_refresh_token
            if self._env_path.exists():
                set_key(str(self._env_path), "MJ_REFRESH_TOKEN", new_refresh_token)

        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in

        self._user_id = self._parse_user_id(self._id_token)

    def _parse_user_id(self, id_token: str) -> str:
        """JWT 페이로드에서 midjourney_id를 추출합니다."""
        try:
            payload_b64 = id_token.split(".")[1]
            # 패딩 보정
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
        """ID 토큰과 refresh 토큰이 모두 포함된 Cookie 헤더 문자열을 반환합니다."""
        self.ensure_valid_token()
        return (
            f"{ID_COOKIE_NAME}={self._id_token}; "
            f"{REFRESH_COOKIE_NAME}={self._refresh_token}"
        )

    def login(self, force: bool = False) -> None:
        """Google OAuth 로그인을 위해 브라우저를 열고 refresh token을 추출합니다.

        매개변수:
            force: True이면 브라우저를 열기 전에 캐시된 브라우저 세션을 초기화합니다.
                   계정을 전환할 때 사용합니다.
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

            # 로그인 완료 대기 — refresh token 쿠키 폴링
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

        # .env에 저장
        if not self._env_path.exists():
            self._env_path.write_text("")
        set_key(str(self._env_path), "MJ_REFRESH_TOKEN", refresh_token)
        print("Login successful!")
        print(f"Refresh token saved to {self._env_path}")
