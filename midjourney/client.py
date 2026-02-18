"""High-level Midjourney client."""

from __future__ import annotations

import os
import time
from pathlib import Path

from curl_cffi import requests as curl_requests

from midjourney.api import MidjourneyAPI
from midjourney.auth import MidjourneyAuth
from midjourney.exceptions import JobFailedError, MidjourneyError
from midjourney.models import Job, UserSettings
from midjourney.params import create_params


class MidjourneyClient:
    """High-level client for generating images with Midjourney.

    Usage:
        client = MidjourneyClient()
        job = client.imagine("a red apple", ar="16:9", stylize=200)
        paths = client.download_images(job, "./images")
    """

    def __init__(
        self,
        refresh_token: str | None = None,
        env_path: str = ".env",
    ):
        self._auth = MidjourneyAuth(refresh_token=refresh_token, env_path=env_path)
        self._api = MidjourneyAPI(self._auth)

    def close(self) -> None:
        self._api.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def user_id(self) -> str:
        return self._auth.user_id

    def login(self) -> None:
        """Open browser for Google OAuth login."""
        self._auth.login()
        self._api.close()
        self._api = MidjourneyAPI(self._auth)

    def _upload_if_local(self, value: str) -> str:
        """If value is a local file path, upload and return CDN URL."""
        if os.path.exists(value):
            print(f"  Uploading {value}...")
            cdn_url = self._api.upload_image(value)
            print(f"  → {cdn_url}")
            return cdn_url
        return value

    def _resolve_image_refs(
        self, image: str | None, params: dict,
    ) -> tuple[str | None, dict[str, int]]:
        """Upload local files for image/sref/oref, return (image_url, metadata).

        Casting to typed params is left to create_params().
        """
        metadata: dict[str, int] = {}

        if image:
            image = self._upload_if_local(image)
            metadata["imagePrompts"] = 1

        if "sref" in params and params["sref"]:
            raw = str(params["sref"])
            params["sref"] = self._upload_if_local(raw)
            if params["sref"].startswith("https://"):
                metadata["imageReferences"] = 1

        if "oref" in params and params["oref"]:
            params["oref"] = self._upload_if_local(str(params["oref"]))
            metadata["characterReferences"] = 1

        return image, metadata

    def imagine(
        self,
        prompt: str,
        *,
        image: str | None = None,
        version: int = 7,
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
        **params,
    ) -> Job:
        """Generate images from a text prompt.

        Args:
            prompt: Text description of the desired image.
            image: Image prompt — local file path or URL.
            version: Midjourney model version (default: 7).
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait for completion.
            mode: Speed mode ('fast', 'relax', 'turbo').
            **params: Version-specific parameters (ar, stylize, chaos, etc.).

        Returns:
            Job object with results (image_urls populated if wait=True).

        Raises:
            ValidationError: If parameters are invalid.
            JobFailedError: If the job fails.
            MidjourneyError: On timeout or other errors.
        """
        image, metadata = self._resolve_image_refs(image, params)

        if image:
            prompt = f"{image} {prompt}"

        p = create_params(version=version, prompt=prompt, **params)
        p.validate()

        job = self._api.submit_job(p, mode=mode, metadata=metadata or None)
        print(f"Job submitted: {job.id}")
        print(f"Prompt: {p.build_prompt()}")

        if not wait:
            return job

        return self._poll_job(job.id, poll_interval, timeout)

    def _poll_job(
        self, job_id: str, interval: float, timeout: float
    ) -> Job:
        """Poll /api/imagine until the job appears (= completed)."""
        start = time.time()
        print("  Waiting for completion...")

        while time.time() - start < timeout:
            job = self._api.get_job_status(job_id)

            if job is not None:
                job.status = "completed"
                job.progress = 100
                if job.id:
                    job.image_urls = [job.cdn_url(i) for i in range(4)]
                print("  Completed!")
                return job

            time.sleep(interval)

        raise MidjourneyError(f"Job {job_id} timed out after {timeout}s")

    def vary(
        self,
        job_id: str,
        index: int,
        strong: bool = True,
        *,
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
    ) -> Job:
        """Create a variation of a generated image."""
        job = self._api.submit_vary(job_id, index, strong=strong, mode=mode)
        label = "Strong" if strong else "Subtle"
        print(f"Vary ({label}) submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def upscale(
        self,
        job_id: str,
        index: int,
        upscale_type: str = "v7_2x_subtle",
        *,
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
    ) -> Job:
        """Upscale a generated image."""
        job = self._api.submit_upscale(
            job_id, index, upscale_type=upscale_type, mode=mode,
        )
        print(f"Upscale ({upscale_type}) submitted: {job.id}")

        if not wait:
            return job

        job = self._poll_job(job.id, poll_interval, timeout)
        job.image_urls = [job.cdn_url(0)]
        return job

    def pan(
        self,
        job_id: str,
        index: int,
        direction: str = "up",
        prompt: str = "",
        *,
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
    ) -> Job:
        """Pan (extend) an image in a direction."""
        job = self._api.submit_pan(
            job_id, index, direction=direction, prompt=prompt, mode=mode,
        )
        print(f"Pan ({direction}) submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def download_images(
        self,
        job: Job,
        output_dir: str = "./images",
        size: int = 640,
        indices: list[int] | None = None,
    ) -> list[Path]:
        """Download generated images to disk."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if indices is None:
            indices = list(range(4))

        paths: list[Path] = []
        for idx in indices:
            url = job.cdn_url(idx, size)
            file_path = out / f"{job.id}_{idx}.webp"

            print(f"Downloading image {idx}...")
            resp = curl_requests.get(url, timeout=60, impersonate="chrome")
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)

            paths.append(file_path)
            print(f"  Saved: {file_path}")

        return paths

    def list_jobs(self, limit: int = 50) -> list[Job]:
        """List recent image generation jobs."""
        jobs = self._api.get_imagine_list(page_size=limit)
        return jobs[:limit]

    def get_settings(self) -> UserSettings:
        """Get current user settings."""
        return self._api.get_user_state()

    def get_queue(self) -> dict:
        """Get current job queue status."""
        return self._api.get_user_queue()
