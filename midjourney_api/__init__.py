"""Midjourney Python API 클라이언트.

사용법:
    from midjourney_api import MidjourneyClient

    with MidjourneyClient() as client:
        job = client.imagine("a red apple", ar="16:9")
        varied = client.vary(job.id, 0, strong=True)
        upscaled = client.upscale(varied.id, 0)
        client.download_images(upscaled, "./images")
"""

from midjourney_api.client import MidjourneyClient
from midjourney_api.exceptions import (
    AuthenticationError,
    JobFailedError,
    MidjourneyError,
    ValidationError,
)
from midjourney_api.models import Job, UserSettings
from midjourney_api.params import create_params

__all__ = [
    "MidjourneyClient",
    "MidjourneyError",
    "AuthenticationError",
    "ValidationError",
    "JobFailedError",
    "Job",
    "UserSettings",
    "create_params",
]
