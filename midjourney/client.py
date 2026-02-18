"""High-level Midjourney client."""

from __future__ import annotations

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
        # Re-create API with refreshed auth
        self._api.close()
        self._api = MidjourneyAPI(self._auth)

    def imagine(
        self,
        prompt: str,
        *,
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
        p = create_params(version=version, prompt=prompt, **params)
        p.validate()

        job = self._api.submit_job(p, mode=mode)
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
                # Job appearing in /api/imagine means it's completed
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
        """Create a variation of a generated image.

        Args:
            job_id: Parent job ID.
            index: Image index in the grid (0-3).
            strong: True for Strong variation, False for Subtle.
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
        """
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
        """Upscale a generated image.

        Args:
            job_id: Parent job ID.
            index: Image index in the grid (0-3).
            upscale_type: 'v7_2x_subtle' or 'v7_2x_creative'.
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
        """
        job = self._api.submit_upscale(
            job_id, index, upscale_type=upscale_type, mode=mode,
        )
        print(f"Upscale ({upscale_type}) submitted: {job.id}")

        if not wait:
            return job

        job = self._poll_job(job.id, poll_interval, timeout)
        # Upscale produces a single image, not a 4-image grid
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
        """Pan (extend) an image in a direction.

        Args:
            job_id: Parent job ID.
            index: Image index in the grid (0-3).
            direction: 'up', 'down', 'left', or 'right'.
            prompt: Prompt text (including parameters) for the panned area.
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
        """
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
        """Download generated images to disk.

        Args:
            job: Completed Job object.
            output_dir: Directory to save images.
            size: Image size (e.g., 640, 1024).
            indices: Which image variants to download (default: all 4).

        Returns:
            List of file paths for downloaded images.
        """
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
        """List recent image generation jobs.

        Args:
            limit: Maximum number of jobs to return.
        """
        jobs = self._api.get_imagine_list(page_size=limit)
        return jobs[:limit]

    def get_settings(self) -> UserSettings:
        """Get current user settings."""
        return self._api.get_user_state()

    def get_queue(self) -> dict:
        """Get current job queue status."""
        return self._api.get_user_queue()
