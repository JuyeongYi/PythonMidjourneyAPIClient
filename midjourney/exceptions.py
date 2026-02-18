"""Midjourney API exceptions."""


class MidjourneyError(Exception):
    """Base exception for all Midjourney errors."""


class AuthenticationError(MidjourneyError):
    """Raised when authentication fails or tokens are invalid/expired."""


class ValidationError(MidjourneyError):
    """Raised when parameter validation fails."""


class JobFailedError(MidjourneyError):
    """Raised when an image generation job fails."""

    def __init__(self, job_id: str, reason: str = ""):
        self.job_id = job_id
        self.reason = reason
        super().__init__(f"Job {job_id} failed: {reason}" if reason else f"Job {job_id} failed")
