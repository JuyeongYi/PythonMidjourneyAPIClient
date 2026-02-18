"""Low-level REST API wrapper for Midjourney."""

from __future__ import annotations

from typing import Any

import httpx

from midjourney.auth import MidjourneyAuth
from midjourney.exceptions import MidjourneyError
from midjourney.models import Job, UserSettings
from midjourney.params.base import BaseParams

BASE_URL = "https://www.midjourney.com"


class MidjourneyAPI:
    """Low-level HTTP client for the Midjourney REST API."""

    def __init__(self, auth: MidjourneyAuth):
        self._auth = auth
        self._client = httpx.Client(base_url=BASE_URL, timeout=30)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an authenticated request."""
        self._auth.ensure_valid_token()
        headers = {**self._auth.get_headers(), **kwargs.pop("headers", {})}
        cookies = {**self._auth.get_cookies(), **kwargs.pop("cookies", {})}

        resp = self._client.request(
            method, path, headers=headers, cookies=cookies, **kwargs
        )
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def submit_job(
        self,
        params: BaseParams,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Submit an image generation job.

        Args:
            params: Validated parameter object (call params.validate() before).
            mode: Speed mode ('fast', 'relax', 'turbo').
            private: Whether to generate in stealth mode.

        Returns:
            A Job with the initial status.
        """
        full_prompt = params.build_prompt()
        user_id = self._auth.user_id

        payload = {
            "t": "imagine",
            "prompt": full_prompt,
            "channelId": f"singleplayer_{user_id}",
            "f": {"mode": mode, "private": private},
            "roomId": None,
            "metadata": {},
        }

        data = self._request("POST", "/api/submit-jobs", json=payload)

        # The response may contain a job_id or job details
        job_id = ""
        if isinstance(data, dict):
            job_id = data.get("job_id", data.get("id", ""))
        elif isinstance(data, list) and data:
            job_id = data[0].get("job_id", data[0].get("id", ""))

        return Job(
            id=job_id,
            prompt=full_prompt,
            status="pending",
            user_id=user_id,
        )

    def get_imagine_update(
        self, checkpoint: str = "", page_size: int = 1000
    ) -> tuple[list[Job], str]:
        """Poll for job status updates.

        Args:
            checkpoint: Cursor from previous call for incremental updates.
            page_size: Number of results per page.

        Returns:
            Tuple of (list of updated Jobs, new checkpoint cursor).
        """
        user_id = self._auth.user_id
        params = {"user_id": user_id, "page_size": page_size}
        if checkpoint:
            params["checkpoint"] = checkpoint

        data = self._request("GET", "/api/imagine-update", params=params)
        jobs = self._parse_jobs(data)
        new_checkpoint = ""
        if isinstance(data, dict):
            new_checkpoint = data.get("checkpoint", "")
        return jobs, new_checkpoint

    def get_imagine_list(self, page_size: int = 1000) -> list[Job]:
        """Fetch the full list of generated images.

        Args:
            page_size: Number of results per page.

        Returns:
            List of Job objects.
        """
        user_id = self._auth.user_id
        data = self._request(
            "GET", "/api/imagine",
            params={"user_id": user_id, "page_size": page_size},
        )
        return self._parse_jobs(data)

    def get_user_queue(self) -> dict:
        """Get the current user's job queue status."""
        return self._request("GET", "/api/user-queue")

    def get_user_state(self) -> UserSettings:
        """Get the current user's mutable settings."""
        data = self._request("GET", "/api/user-mutable-state")
        if not isinstance(data, dict):
            data = {}
        return UserSettings(
            user_id=self._auth.user_id,
            subscription_type=data.get("subscription_type", ""),
            fast_time_remaining=data.get("fast_time_remaining", 0.0),
            relax_enabled=data.get("relax_enabled", False),
            stealth_enabled=data.get("stealth_enabled", False),
            raw_data=data,
        )

    def _parse_jobs(self, data: Any) -> list[Job]:
        """Parse API response into Job objects."""
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("jobs", data.get("items", data.get("data", [])))
            if not isinstance(items, list):
                items = []

        jobs = []
        for item in items:
            if not isinstance(item, dict):
                continue
            job = Job(
                id=item.get("id", item.get("job_id", "")),
                prompt=item.get("prompt", item.get("full_command", "")),
                status=self._normalize_status(item.get("current_status", item.get("status", ""))),
                progress=item.get("percentage_complete", 0),
                user_id=item.get("user_id", ""),
                enqueue_time=item.get("enqueue_time"),
            )
            # Build image URLs if completed
            if job.is_completed and job.id:
                job.image_urls = [job.cdn_url(i) for i in range(4)]
            jobs.append(job)
        return jobs

    @staticmethod
    def _normalize_status(raw: str) -> str:
        status_map = {
            "completed": "completed",
            "complete": "completed",
            "done": "completed",
            "failed": "failed",
            "error": "failed",
            "cancelled": "failed",
            "running": "running",
            "generating": "running",
            "in_progress": "running",
            "pending": "pending",
            "queued": "pending",
            "enqueued": "pending",
            "waiting": "pending",
        }
        return status_map.get(raw.lower(), raw.lower()) if raw else "pending"
