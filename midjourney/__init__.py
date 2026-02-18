"""Midjourney Python API Client.

Usage:
    from midjourney import MidjourneyClient

    with MidjourneyClient() as client:
        job = client.imagine("a red apple", ar="16:9")
        varied = client.vary(job.id, 0, strong=True)
        upscaled = client.upscale(varied.id, 0)
        client.download_images(upscaled, "./images")
"""

from midjourney.client import MidjourneyClient
from midjourney.exceptions import (
    AuthenticationError,
    JobFailedError,
    MidjourneyError,
    ValidationError,
)
from midjourney.models import Job, UserSettings
from midjourney.params import create_params

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
