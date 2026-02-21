"""High-level Midjourney client."""

from __future__ import annotations

import os
import time
from pathlib import Path

from curl_cffi import requests as curl_requests

from midjourney_api.api import MidjourneyAPI
from midjourney_api.auth import MidjourneyAuth
from midjourney_api.const import UpscaleType
from midjourney_api.exceptions import MidjourneyError
from midjourney_api.models import Job, UserSettings
from midjourney_api.params import create_params


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
        print_log: bool = False,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ):
        self._auth = MidjourneyAuth(refresh_token=refresh_token, env_path=env_path)
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._api = MidjourneyAPI(
            self._auth, max_retries=max_retries, retry_backoff=retry_backoff,
        )
        self._print_log = print_log

    def _log(self, msg: str) -> None:
        if self._print_log:
            print(msg)

    def close(self) -> None:
        self._api.close()

    def __enter__(self) -> MidjourneyClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    @property
    def user_id(self) -> str:
        return self._auth.user_id

    def login(self, force: bool = False) -> None:
        """Open browser for Google OAuth login.

        Args:
            force: If True, clear the cached browser session before opening.
                   Use this to switch accounts.
        """
        self._auth.login(force=force)
        self._api.close()
        self._api = MidjourneyAPI(
            self._auth,
            max_retries=self._max_retries,
            retry_backoff=self._retry_backoff,
        )

    def _upload_if_local(self, value: str) -> str:
        """If value is a local file path, upload and return CDN URL."""
        if os.path.exists(value):
            self._log(f"  Uploading {value}...")
            cdn_url = self._api.upload_image(value)
            self._log(f"  → {cdn_url}")
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
        self._log(f"Job submitted: {job.id}")
        self._log(f"Prompt: {p.build_prompt()}")

        if not wait:
            return job

        return self._poll_job(job.id, poll_interval, timeout)

    def _poll_job(
        self, job_id: str, interval: float, timeout: float
    ) -> Job:
        """Poll /api/imagine until the job appears (= completed)."""
        start = time.time()
        self._log("  Waiting for completion...")

        while time.time() - start < timeout:
            job = self._api.get_job_status(job_id)

            if job is not None:
                job.status = "completed"
                job.progress = 100
                if job.id:
                    job.image_urls = [job.cdn_url(i) for i in range(4)]
                self._log("  Completed!")
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
        self._log(f"Vary ({label}) submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def upscale(
        self,
        job_id: str,
        index: int,
        upscale_type: str = UpscaleType.SUBTLE,
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
        self._log(f"Upscale ({upscale_type}) submitted: {job.id}")

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
        self._log(f"Pan ({direction}) submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def animate(
        self,
        job_id: str,
        index: int,
        *,
        prompt: str = "",
        end_image: str | None = None,
        motion: str | None = None,
        batch_size: int = 1,
        resolution: str = "480",
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
        stealth: bool = False,
    ) -> Job:
        """Generate an animation from a completed imagine job.

        Args:
            job_id: Completed imagine job ID.
            index: Image index within the grid (0-3).
            prompt: Optional additional prompt text.
            end_image: Local file or URL for the end frame. If provided, uses
                       ``vid_1.1_i2v_start_end`` with ``--end {url}``.
            motion: Motion intensity ("low" or "high").
            batch_size: Number of video variants to generate (``--bs N``). Default 1.
            resolution: Video resolution ('480' or '720').
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
            stealth: If True, generate in stealth (private) mode.

        Returns:
            Completed Job with video_url()/gif_url() available.
        """
        end_url = self._upload_if_local(end_image) if end_image else None
        job = self._api.submit_animate(
            job_id, index, prompt=prompt, end_url=end_url, motion=motion,
            batch_size=batch_size, resolution=resolution, mode=mode, private=stealth,
        )
        self._log(f"Animate submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def animate_from_image(
        self,
        start_image: str,
        end_image: str | None = None,
        *,
        motion: str | None = None,
        prompt: str = "",
        batch_size: int = 1,
        resolution: str = "480",
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
        stealth: bool = False,
    ) -> Job:
        """Generate an animation from image files.

        Modes:
        - Single image (end_image=None):    ``vid_1.1_i2v``
        - Start+end (end_image=<file/URL>): ``vid_1.1_i2v_start_end``
        - Start+loop (end_image="loop"):    ``vid_1.1_i2v_start_end``, ``--motion {motion}``

        Args:
            start_image: Local file or URL for the start frame (auto-uploaded if local).
            end_image: Local file/URL for end frame, "loop" for loop mode, or None.
            motion: Motion intensity ("low" or "high").
            prompt: Optional text prompt.
            batch_size: Number of video variants (``--bs N``). Default 1.
            resolution: Video resolution ('480' or '720').
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
            stealth: If True, generate in stealth (private) mode.

        Returns:
            Completed Job with video_url()/gif_url() available.
        """
        start_url = self._upload_if_local(start_image)
        end_url: str | None
        if end_image is None or end_image == "loop":
            end_url = end_image  # None or "loop" — not a file path
        else:
            end_url = self._upload_if_local(end_image)

        job = self._api.submit_animate_from_image(
            start_url, end_url=end_url, motion=motion,
            prompt=prompt, batch_size=batch_size, resolution=resolution,
            mode=mode, private=stealth,
        )
        self._log(f"Animate from image submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def extend_video(
        self,
        job_id: str,
        index: int = 0,
        *,
        end_image: str | None = None,
        motion: str | None = None,
        batch_size: int = 1,
        resolution: str = "480",
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
        stealth: bool = False,
        prompt: str = "",
    ) -> Job:
        """Extend a completed video job.

        Args:
            job_id: Completed video job ID to extend.
            index: Batch variant index to extend (default 0).
            prompt: Optional text prompt to guide the extension direction.
            end_image: End frame (local file/URL) or "loop" for seamless loop.
                       None = just extend. Switches to vid_1.1_i2v_start_end mode.
            motion: Motion intensity ("low" or "high").
            batch_size: Number of video variants (``--bs N``). Default 1.
            resolution: Video resolution ('480' or '720').
            wait: If True, poll until the job completes.
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.
            mode: Speed mode ('fast', 'relax', 'turbo').
            stealth: If True, generate in stealth (private) mode.

        Returns:
            Completed Job with video_url()/gif_url() available.
        """
        if end_image and end_image != "loop":
            end_url: str | None = self._upload_if_local(end_image)
        else:
            end_url = end_image  # None or "loop"
        job = self._api.submit_extend_video(
            job_id, index=index, end_url=end_url, motion=motion,
            batch_size=batch_size, resolution=resolution, mode=mode, private=stealth,
            prompt=prompt,
        )
        self._log(f"Extend video submitted: {job.id}")

        if not wait:
            return job
        return self._poll_job(job.id, poll_interval, timeout)

    def download_video(
        self,
        job: Job,
        output_dir: str = "./videos",
        size: int | None = None,
        batch_size: int = 1,
    ) -> list[Path]:
        """Download a completed animation video to disk.

        Args:
            job: Completed video Job.
            output_dir: Directory to save the video.
            size: Resolution (e.g. 1080 for social). None = raw original.
            batch_size: Number of variants to download (matches --batch-size used at submit).

        Returns:
            List of paths to saved .mp4 files.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        size_suffix = f"_{size}" if size else ""
        paths: list[Path] = []

        for i in range(batch_size):
            url = job.video_url(index=i, size=size)
            file_path = out / f"{job.id}_{i}{size_suffix}.mp4"

            self._log(f"Downloading video {i}...")
            resp = curl_requests.get(url, timeout=120, impersonate="chrome")
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)

            self._log(f"  Saved: {file_path}")
            paths.append(file_path)

        return paths

    def download_video_bytes(
        self,
        job: Job,
        size: int | None = None,
        batch_size: int = 1,
    ) -> list[bytes]:
        """Download a completed animation video as raw bytes (no disk I/O).

        Args:
            job: Completed video Job.
            size: Resolution (e.g. 1080 for social). None = raw original.
            batch_size: Number of variants to download (matches --batch-size used at submit).

        Returns:
            List of raw MP4 bytes, one per batch variant.
        """
        result: list[bytes] = []
        for i in range(batch_size):
            url = job.video_url(index=i, size=size)
            resp = curl_requests.get(url, timeout=120, impersonate="chrome")
            resp.raise_for_status()
            result.append(resp.content)
        return result

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
            count = len(job.image_urls) if job.image_urls else 4
            indices = list(range(count))

        paths: list[Path] = []
        for idx in indices:
            url = job.cdn_url(idx, size)
            file_path = out / f"{job.id}_{idx}.webp"

            self._log(f"Downloading image {idx}...")
            resp = curl_requests.get(url, timeout=60, impersonate="chrome")
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)

            paths.append(file_path)
            self._log(f"  Saved: {file_path}")

        return paths

    def download_images_bytes(
        self,
        job: Job,
        size: int = 640,
        indices: list[int] | None = None,
    ) -> list[bytes]:
        """Download generated images as raw bytes (no disk I/O)."""
        if indices is None:
            count = len(job.image_urls) if job.image_urls else 4
            indices = list(range(count))

        result: list[bytes] = []
        for idx in indices:
            url = job.cdn_url(idx, size)
            resp = curl_requests.get(url, timeout=60, impersonate="chrome")
            resp.raise_for_status()
            result.append(resp.content)

        return result

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
