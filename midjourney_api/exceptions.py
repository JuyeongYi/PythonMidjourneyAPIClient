"""Midjourney API 예외 클래스."""


class MidjourneyError(Exception):
    """모든 Midjourney 오류의 기본 예외."""


class AuthenticationError(MidjourneyError):
    """인증 실패 또는 토큰이 유효하지 않거나 만료된 경우 발생."""


class ValidationError(MidjourneyError):
    """파라미터 유효성 검사 실패 시 발생."""


class JobFailedError(MidjourneyError):
    """이미지 생성 작업 실패 시 발생."""

    def __init__(self, job_id: str, reason: str = ""):
        self.job_id = job_id
        self.reason = reason
        super().__init__(f"Job {job_id} failed: {reason}" if reason else f"Job {job_id} failed")
