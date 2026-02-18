"""Low-level REST API wrapper for Midjourney."""

from __future__ import annotations

import json as json_mod
from typing import Any

from curl_cffi import requests as curl_requests

from midjourney.auth import MidjourneyAuth
from midjourney.exceptions import MidjourneyError
from midjourney.models import Job, UserSettings
from midjourney.params.base import BaseParams

BASE_URL = "https://www.midjourney.com"


class MidjourneyAPI:
    """Low-level HTTP client for the Midjourney REST API.

    Uses curl_cffi to impersonate Chrome's TLS fingerprint,
    bypassing Cloudflare bot protection.
    """

    def __init__(self, auth: MidjourneyAuth):
        self._auth = auth
        self._session = curl_requests.Session(impersonate="chrome")

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an authenticated request."""
        self._auth.ensure_valid_token()

        url = f"{BASE_URL}{path}"
        headers = {
            "x-csrf-protection": "1",
            "Cookie": self._auth.cookie_header(),
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/imagine",
            **kwargs.pop("headers", {}),
        }
        kwargs.pop("cookies", None)

        # curl_cffi uses 'data' for form and 'json' kwarg doesn't exist;
        # serialize JSON manually
        json_body = kwargs.pop("json", None)
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            kwargs["data"] = json_mod.dumps(json_body)

        resp = self._session.request(
            method, url, headers=headers, timeout=30, **kwargs
        )
        if resp.status_code >= 400:
            cookie_hdr = self._auth.cookie_header()
            print(f"[DEBUG] {method} {path} → {resp.status_code}")
            print(f"[DEBUG] Cookie: {cookie_hdr[:80]}...({len(cookie_hdr)} chars)")
            print(f"[DEBUG] User ID: {self._auth.user_id}")
            print(f"[DEBUG] Response: {resp.text[:500]}")
            resp.raise_for_status()
        return resp.json() if resp.content else None

    def submit_job(
        self,
        params: BaseParams,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Submit an image generation job."""
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

        # Response: {"success": [{"job_id": "..."}], "failure": []}
        job_id = ""
        if isinstance(data, dict):
            success = data.get("success", [])
            if success:
                job_id = success[0].get("job_id", "")
            else:
                job_id = data.get("job_id", data.get("id", ""))

        return Job(
            id=job_id,
            prompt=full_prompt,
            status="pending",
            user_id=user_id,
        )

    def get_job_status(self, job_id: str) -> Job | None:
        """Check if a job appears in the imagine list (= completed)."""
        user_id = self._auth.user_id
        data = self._request(
            "GET", "/api/imagine",
            params={"user_id": user_id, "page_size": 100},
        )

        raw_items = data if isinstance(data, list) else []
        if isinstance(data, dict):
            for key in ("jobs", "items", "data"):
                if key in data and isinstance(data[key], list):
                    raw_items = data[key]
                    break

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id", item.get("job_id", ""))
            if item_id == job_id:
                return Job(
                    id=item_id,
                    prompt=item.get("prompt", item.get("full_command", "")),
                    status="completed",
                    progress=100,
                    user_id=item.get("user_id", ""),
                )
        return None

    def get_imagine_list(self, page_size: int = 1000) -> list[Job]:
        """Fetch the full list of generated images."""
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
