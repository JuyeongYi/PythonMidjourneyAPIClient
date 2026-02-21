"""Midjourney API 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from midjourney_api.const import CDN_VIDEO_BASE


@dataclass
class Job:
    """Midjourney 이미지 생성 작업을 나타냅니다."""

    id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    progress: int = 0
    image_urls: list[str] = field(default_factory=list)
    user_id: str = ""
    enqueue_time: str | None = None
    parent_id: str | None = None
    event_type: str | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_video(self) -> bool:
        """비디오/애니메이션 작업이면 True를 반환합니다."""
        return "video" in (self.event_type or "")

    def video_url(self, index: int = 0, size: int | None = None) -> str:
        """비디오 파일의 CDN URL을 빌드합니다.

        매개변수:
            index: 배치 인덱스 (batch_size=1이면 항상 0).
            size: 해상도 (예: 소셜용 1080). None = 원본 그대로.
        """
        if size:
            return f"{CDN_VIDEO_BASE}/{self.id}/{index}_{size}_N.mp4"
        return f"{CDN_VIDEO_BASE}/{self.id}/{index}.mp4"

    def gif_url(self, index: int = 0) -> str:
        """비디오 작업의 GIF 버전 CDN URL을 빌드합니다."""
        return f"{CDN_VIDEO_BASE}/{self.id}/{index}_N.gif"

    def cdn_url(self, index: int = 0, size: int = 640) -> str:
        """특정 이미지 변형의 CDN URL을 빌드합니다.

        매개변수:
            index: 이미지 변형 인덱스 (그리드 이미지는 0-3).
            size: 이미지 크기 (예: 640, 1024).
        """
        return (
            f"https://cdn.midjourney.com/{self.id}/0_{index}_{size}_N.webp"
            f"?method=shortest"
        )


@dataclass
class UserSettings:
    """Midjourney 사용자 가변 상태를 나타냅니다."""

    user_id: str
    subscription_type: str = ""
    fast_time_remaining: float = 0.0
    relax_enabled: bool = False
    stealth_enabled: bool = False
    raw_data: dict = field(default_factory=dict)
