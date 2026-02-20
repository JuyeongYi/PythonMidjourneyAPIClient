"""Data models for the Midjourney API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """Represents a Midjourney image generation job."""

    id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    progress: int = 0
    image_urls: list[str] = field(default_factory=list)
    user_id: str = ""
    enqueue_time: Optional[str] = None
    parent_id: Optional[str] = None
    event_type: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_video(self) -> bool:
        """True if this job is a video/animation job."""
        return "video" in (self.event_type or "")

    def video_url(self, index: int = 0, size: int | None = None) -> str:
        """Build CDN URL for a video file.

        Args:
            index: Batch index (always 0 for batch_size=1).
            size: Resolution (e.g. 1080 for social). None = raw original.
        """
        if size:
            return f"https://cdn.midjourney.com/video/{self.id}/{index}_{size}_N.mp4"
        return f"https://cdn.midjourney.com/video/{self.id}/{index}.mp4"

    def gif_url(self, index: int = 0) -> str:
        """Build CDN URL for a GIF version of a video job."""
        return f"https://cdn.midjourney.com/video/{self.id}/{index}_N.gif"

    def cdn_url(self, index: int = 0, size: int = 640) -> str:
        """Build CDN URL for a specific image variant.

        Args:
            index: Image variant index (0-3 for grid images).
            size: Image size (e.g., 640, 1024).
        """
        return (
            f"https://cdn.midjourney.com/{self.id}/0_{index}_{size}_N.webp"
            f"?method=shortest"
        )


@dataclass
class UserSettings:
    """Represents Midjourney user mutable state."""

    user_id: str
    subscription_type: str = ""
    fast_time_remaining: float = 0.0
    relax_enabled: bool = False
    stealth_enabled: bool = False
    raw_data: dict = field(default_factory=dict)
