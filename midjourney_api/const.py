"""Constants and enumerations for the Midjourney API client."""

from __future__ import annotations

from enum import IntEnum, StrEnum

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

BASE_URL = "https://www.midjourney.com"
CDN_BASE = "https://cdn.midjourney.com/u"
CDN_VIDEO_BASE = "https://cdn.midjourney.com/video"

# ---------------------------------------------------------------------------
# Firebase Auth
# ---------------------------------------------------------------------------

FIREBASE_API_KEY = "AIzaSyAjizp68NsH3JGUS0EyLXsChW4fN0A92tM"
FIREBASE_TOKEN_URL = (
    f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
)

# ---------------------------------------------------------------------------
# Cookie names
# ---------------------------------------------------------------------------

REFRESH_COOKIE_NAME = "__Host-Midjourney.AuthUserTokenV3_r"
ID_COOKIE_NAME = "__Host-Midjourney.AuthUserTokenV3_i"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VideoResolution(StrEnum):
    """Supported video generation resolutions."""

    R480 = "480"
    R720 = "720"


class UpscaleType(StrEnum):
    """Supported upscale types."""

    SUBTLE = "v7_2x_subtle"
    CREATIVE = "v7_2x_creative"


class PanDirection(IntEnum):
    """Pan direction codes used by the Midjourney API."""

    DOWN = 0
    RIGHT = 1
    UP = 2
    LEFT = 3
