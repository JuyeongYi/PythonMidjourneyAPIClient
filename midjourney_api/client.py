"""Midjourney 고수준 클라이언트."""

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
    """Midjourney로 이미지를 생성하는 고수준 클라이언트.

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
        """Google OAuth 로그인을 위해 브라우저를 엽니다.

        매개변수:
            force: True이면 브라우저를 열기 전에 캐시된 세션을 초기화합니다.
                   계정을 전환할 때 사용하세요.
        """
        self._auth.login(force=force)
        self._api.close()
        self._api = MidjourneyAPI(
            self._auth,
            max_retries=self._max_retries,
            retry_backoff=self._retry_backoff,
        )

    def _upload_if_local(self, value: str) -> str:
        """값이 로컬 파일 경로인 경우 업로드하고 CDN URL을 반환합니다."""
        if os.path.exists(value):
            self._log(f"  Uploading {value}...")
            cdn_url = self._api.upload_image(value)
            self._log(f"  → {cdn_url}")
            return cdn_url
        return value

    def _resolve_image_refs(
        self, image: str | None, params: dict,
    ) -> tuple[str | None, dict[str, int]]:
        """image/sref/oref의 로컬 파일을 업로드하고 (image_url, metadata)를 반환합니다.

        타입 파라미터로의 캐스팅은 create_params()에 위임합니다.
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
        """텍스트 프롬프트로 이미지를 생성합니다.

        매개변수:
            prompt: 원하는 이미지에 대한 텍스트 설명.
            image: 이미지 프롬프트 — 로컬 파일 경로 또는 URL.
            version: Midjourney 모델 버전 (기본값: 7).
            wait: True이면 작업이 완료될 때까지 폴링합니다.
            poll_interval: 상태 폴링 간격 (초).
            timeout: 완료를 기다리는 최대 시간 (초).
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            **params: 버전별 파라미터 (ar, stylize, chaos 등).

        반환값:
            결과가 담긴 Job 객체 (wait=True인 경우 image_urls 포함).

        예외:
            ValidationError: 파라미터가 유효하지 않은 경우.
            JobFailedError: 작업이 실패한 경우.
            MidjourneyError: 타임아웃 또는 기타 오류 발생 시.
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
        """/api/imagine을 작업이 나타날 때까지 폴링합니다 (= 완료)."""
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
        """생성된 이미지의 변형을 생성합니다."""
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
        """생성된 이미지를 업스케일합니다."""
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
        """이미지를 특정 방향으로 팬(확장)합니다."""
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
        """완료된 imagine 작업으로부터 애니메이션을 생성합니다.

        매개변수:
            job_id: 완료된 imagine 작업 ID.
            index: 그리드 내 이미지 인덱스 (0-3).
            prompt: 선택적 추가 프롬프트 텍스트.
            end_image: 끝 프레임의 로컬 파일 또는 URL. 제공 시
                       ``vid_1.1_i2v_start_end``와 ``--end {url}``을 사용합니다.
            motion: 모션 강도 ("low" 또는 "high").
            batch_size: 생성할 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            wait: True이면 작업이 완료될 때까지 폴링합니다.
            poll_interval: 상태 폴링 간격 (초).
            timeout: 대기할 최대 시간 (초).
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            stealth: True이면 스텔스(비공개) 모드로 생성합니다.

        반환값:
            video_url()/gif_url()을 사용할 수 있는 완료된 Job.
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
        """이미지 파일로부터 애니메이션을 생성합니다.

        모드:
        - 단일 이미지 (end_image=None):      ``vid_1.1_i2v``
        - 시작+끝 (end_image=<파일/URL>):    ``vid_1.1_i2v_start_end``
        - 시작+루프 (end_image="loop"):      ``vid_1.1_i2v_start_end``, ``--motion {motion}``

        매개변수:
            start_image: 시작 프레임의 로컬 파일 또는 URL (로컬인 경우 자동 업로드).
            end_image: 끝 프레임의 로컬 파일/URL, 루프 모드의 경우 "loop", 또는 None.
            motion: 모션 강도 ("low" 또는 "high").
            prompt: 선택적 텍스트 프롬프트.
            batch_size: 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            wait: True이면 작업이 완료될 때까지 폴링합니다.
            poll_interval: 상태 폴링 간격 (초).
            timeout: 대기할 최대 시간 (초).
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            stealth: True이면 스텔스(비공개) 모드로 생성합니다.

        반환값:
            video_url()/gif_url()을 사용할 수 있는 완료된 Job.
        """
        start_url = self._upload_if_local(start_image)
        end_url: str | None
        if end_image is None or end_image == "loop":
            end_url = end_image  # None 또는 'loop' — 파일 경로가 아님
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
        prompt: str = "",
        batch_size: int = 1,
        resolution: str = "480",
        wait: bool = True,
        poll_interval: float = 5,
        timeout: float = 600,
        mode: str = "fast",
        stealth: bool = False,
    ) -> Job:
        """완료된 비디오 작업을 연장합니다.

        매개변수:
            job_id: 연장할 완료된 비디오 작업 ID.
            index: 연장할 배치 변형 인덱스 (기본값 0).
            prompt: 연장 방향을 안내하는 선택적 텍스트 프롬프트.
            end_image: 끝 프레임 (로컬 파일/URL) 또는 매끄러운 루프를 위한 "loop".
                       None = 단순 연장. vid_1.1_i2v_start_end 모드로 전환됩니다.
            motion: 모션 강도 ("low" 또는 "high").
            batch_size: 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            wait: True이면 작업이 완료될 때까지 폴링합니다.
            poll_interval: 상태 폴링 간격 (초).
            timeout: 대기할 최대 시간 (초).
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            stealth: True이면 스텔스(비공개) 모드로 생성합니다.

        반환값:
            video_url()/gif_url()을 사용할 수 있는 완료된 Job.
        """
        if end_image and end_image != "loop":
            end_url: str | None = self._upload_if_local(end_image)
        else:
            end_url = end_image  # None 또는 'loop'
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
        """완료된 애니메이션 비디오를 디스크에 다운로드합니다.

        매개변수:
            job: 완료된 비디오 Job.
            output_dir: 비디오를 저장할 디렉토리.
            size: 해상도 (예: 소셜용 1080). None = 원본 그대로.
            batch_size: 다운로드할 변형 수 (제출 시 사용한 --batch-size와 일치).

        반환값:
            저장된 .mp4 파일 경로 목록.
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
        """완료된 애니메이션 비디오를 바이트로 다운로드합니다 (디스크 I/O 없음).

        매개변수:
            job: 완료된 비디오 Job.
            size: 해상도 (예: 소셜용 1080). None = 원본 그대로.
            batch_size: 다운로드할 변형 수 (제출 시 사용한 --batch-size와 일치).

        반환값:
            배치 변형별 원시 MP4 바이트 목록.
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
        """생성된 이미지를 디스크에 다운로드합니다."""
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
        """생성된 이미지를 바이트로 다운로드합니다 (디스크 I/O 없음)."""
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
        """최근 이미지 생성 작업을 나열합니다."""
        jobs = self._api.get_imagine_list(page_size=limit)
        return jobs[:limit]

    def get_settings(self) -> UserSettings:
        """현재 사용자 설정을 가져옵니다."""
        return self._api.get_user_state()

    def get_queue(self) -> dict:
        """현재 작업 큐 상태를 가져옵니다."""
        return self._api.get_user_queue()
