"""Midjourney API 클라이언트 상수 및 열거형."""

from __future__ import annotations

from enum import IntEnum, StrEnum

# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

BASE_URL = "https://www.midjourney.com"
CDN_BASE = "https://cdn.midjourney.com/u"
CDN_VIDEO_BASE = "https://cdn.midjourney.com/video"

# ---------------------------------------------------------------------------
# Firebase 인증
# ---------------------------------------------------------------------------

FIREBASE_API_KEY = "AIzaSyAjizp68NsH3JGUS0EyLXsChW4fN0A92tM"
FIREBASE_TOKEN_URL = (
    f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
)

# ---------------------------------------------------------------------------
# 쿠키 이름
# ---------------------------------------------------------------------------

REFRESH_COOKIE_NAME = "__Host-Midjourney.AuthUserTokenV3_r"
ID_COOKIE_NAME = "__Host-Midjourney.AuthUserTokenV3_i"

# ---------------------------------------------------------------------------
# 열거형
# ---------------------------------------------------------------------------


class VideoResolution(StrEnum):
    """지원하는 비디오 생성 해상도."""

    R480 = "480"
    R720 = "720"


class UpscaleType(StrEnum):
    """지원하는 업스케일 유형."""

    SUBTLE = "v7_2x_subtle"
    CREATIVE = "v7_2x_creative"


class PanDirection(IntEnum):
    """Midjourney API에서 사용하는 팬 방향 코드."""

    DOWN = 0
    RIGHT = 1
    UP = 2
    LEFT = 3
