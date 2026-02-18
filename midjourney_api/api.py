"""Low-level REST API wrapper for Midjourney."""

from __future__ import annotations

import json as json_mod
import mimetypes
from pathlib import Path
from typing import Any

from curl_cffi import requests as curl_requests
from curl_cffi.curl import CurlMime

from midjourney_api.auth import MidjourneyAuth
from midjourney_api.exceptions import MidjourneyError
from midjourney_api.models import Job, UserSettings
from midjourney_api.params.base import BaseParams

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

    CDN_BASE = "https://cdn.midjourney.com/u"

    def upload_image(self, file_path: str) -> str:
        """Upload a local image file and return its CDN URL.

        Uses /api/storage-upload-file with multipart/form-data.
        """
        self._auth.ensure_valid_token()

        path = Path(file_path).resolve()
        content_type = mimetypes.guess_type(str(path))[0] or "image/png"
        mp = CurlMime()
        mp.addpart(
            name="file",
            filename=path.name,
            local_path=str(path),
            content_type=content_type,
        )

        url = f"{BASE_URL}/api/storage-upload-file"
        headers = {
            "x-csrf-protection": "1",
            "Cookie": self._auth.cookie_header(),
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/imagine",
        }
        resp = self._session.post(
            url,
            headers=headers,
            multipart=mp,
            timeout=60,
        )
        if resp.status_code >= 400:
            print(f"[DEBUG] POST /api/storage-upload-file → {resp.status_code}")
            print(f"[DEBUG] Response: {resp.text[:500]}")
            resp.raise_for_status()

        data = resp.json()
        bucket_pathname = data["bucketPathname"]
        return f"{self.CDN_BASE}/{bucket_pathname}"

    def submit_job(
        self,
        params: BaseParams,
        mode: str = "fast",
        private: bool = False,
        metadata: dict | None = None,
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
            "metadata": metadata or {},
        }

        data = self._request("POST", "/api/submit-jobs", json=payload)

        # Response: {"success": [{"job_id": "..."}], "failure": [...]}
        job_id = ""
        if isinstance(data, dict):
            failures = data.get("failure", [])
            if failures:
                fail = failures[0]
                raise MidjourneyError(
                    f"Job rejected: {fail.get('message', 'unknown error')}"
                )
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

    # -- Post-processing methods ------------------------------------------

    DIRECTION_MAP = {"up": 0, "right": 1, "down": 2, "left": 3}

    def _submit_postprocess(
        self,
        job_id: str,
        index: int,
        task_type: str,
        extra: dict,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Submit a post-processing job (vary/upscale/pan)."""
        user_id = self._auth.user_id

        payload = {
            "t": task_type,
            "id": job_id,
            "index": index,
            "channelId": f"singleplayer_{user_id}",
            "f": {"mode": mode, "private": private},
            "roomId": None,
            "metadata": {"isMobile": None, "imagePrompts": None},
            **extra,
        }

        data = self._request("POST", "/api/submit-jobs", json=payload)

        new_job_id = ""
        prompt = ""
        parent_id = job_id
        if isinstance(data, dict):
            success = data.get("success", [])
            if success:
                new_job_id = success[0].get("job_id", "")
                prompt = success[0].get("prompt", "")
                meta = success[0].get("meta", {})
                parent_id = meta.get("parent_id", job_id)

        return Job(
            id=new_job_id,
            prompt=prompt,
            status="pending",
            user_id=user_id,
            parent_id=parent_id,
        )

    def submit_vary(
        self, job_id: str, index: int, strong: bool = True,
        mode: str = "fast", private: bool = False,
    ) -> Job:
        """Submit a Vary (Strong/Subtle) job."""
        return self._submit_postprocess(
            job_id, index, "vary",
            extra={"strong": strong},
            mode=mode, private=private,
        )

    def submit_upscale(
        self, job_id: str, index: int, upscale_type: str = "v7_2x_subtle",
        mode: str = "fast", private: bool = False,
    ) -> Job:
        """Submit an Upscale job."""
        return self._submit_postprocess(
            job_id, index, "upscale",
            extra={"type": upscale_type},
            mode=mode, private=private,
        )

    def submit_pan(
        self, job_id: str, index: int, direction: str = "up",
        prompt: str = "", mode: str = "fast", private: bool = False,
    ) -> Job:
        """Submit a Pan job."""
        return self._submit_postprocess(
            job_id, index, "pan",
            extra={
                "direction": self.DIRECTION_MAP[direction],
                "newPrompt": prompt,
                "fraction": 0.5,
                "stitch": True,
            },
            mode=mode, private=private,
        )

    # -- Job status & listing ----------------------------------------------

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
