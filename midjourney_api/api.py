"""Midjourney REST API 저수준 래퍼."""

from __future__ import annotations

import json as json_mod
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests as curl_requests
from curl_cffi.curl import CurlMime

from midjourney_api.auth import MidjourneyAuth
from midjourney_api.const import BASE_URL, CDN_BASE, PanDirection, UpscaleType, VideoResolution
from midjourney_api.exceptions import MidjourneyError
from midjourney_api.models import Job, UserSettings
from midjourney_api.params.base import BaseParams

logger = logging.getLogger(__name__)


class MidjourneyAPI:
    """Midjourney REST API 저수준 HTTP 클라이언트.

    curl_cffi를 사용하여 Chrome의 TLS 핑거프린트를 모방함으로써
    Cloudflare 봇 보호를 우회합니다.
    """

    def __init__(
        self,
        auth: MidjourneyAuth,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ):
        self._auth = auth
        self._session = curl_requests.Session(impersonate="chrome")
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """인증된 요청을 수행합니다."""
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

        # curl_cffi는 폼 데이터에 'data'를 사용하며 'json' 키워드 인자가 없으므로
        # JSON을 수동으로 직렬화합니다
        json_body = kwargs.pop("json", None)
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            kwargs["data"] = json_mod.dumps(json_body)

        last_exc: Exception | None = None
        resp = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                wait = self._retry_backoff * (2 ** (attempt - 1))
                logger.debug("Retry %d/%d after %.1fs", attempt, self._max_retries, wait)
                time.sleep(wait)
            try:
                resp = self._session.request(
                    method, url, headers=headers, timeout=30, **kwargs
                )
            except Exception as e:
                last_exc = e
                logger.debug("Network error (attempt %d): %s", attempt + 1, e)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", self._retry_backoff))
                logger.debug("429 Rate limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                last_exc = None
                continue
            if resp.status_code >= 500 and attempt < self._max_retries:
                last_exc = None
                continue
            last_exc = None
            break

        if last_exc:
            raise MidjourneyError(
                f"Request failed after {self._max_retries} retries: {last_exc}"
            ) from last_exc

        if resp is None:
            raise MidjourneyError("Request failed: no response received")

        if resp.status_code >= 400:
            cookie_hdr = self._auth.cookie_header()
            logger.debug("%s %s → %s", method, path, resp.status_code)
            logger.debug("Cookie: %s...(%d chars)", cookie_hdr[:80], len(cookie_hdr))
            logger.debug("User ID: %s", self._auth.user_id)
            logger.debug("Response: %s", resp.text[:500])
            resp.raise_for_status()
        return resp.json() if resp.content else None

    def upload_image(self, file_path: str) -> str:
        """로컬 이미지 파일을 업로드하고 CDN URL을 반환합니다.

        /api/storage-upload-file에 multipart/form-data 형식으로 업로드합니다.
        네트워크 오류와 5xx 응답에 대해 max_retries 횟수만큼 재시도합니다.
        """
        path = Path(file_path).resolve()
        content_type = mimetypes.guess_type(str(path))[0] or "image/png"
        url = f"{BASE_URL}/api/storage-upload-file"

        last_exc: Exception | None = None
        resp = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                wait = self._retry_backoff * (2 ** (attempt - 1))
                logger.debug("Upload retry %d/%d after %.1fs", attempt, self._max_retries, wait)
                time.sleep(wait)

            self._auth.ensure_valid_token()
            headers = {
                "x-csrf-protection": "1",
                "Cookie": self._auth.cookie_header(),
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/imagine",
            }
            # CurlMime는 일회성이므로 재시도마다 새로 생성합니다
            mp = CurlMime()
            mp.addpart(
                name="file",
                filename=path.name,
                local_path=str(path),
                content_type=content_type,
            )
            try:
                resp = self._session.post(url, headers=headers, multipart=mp, timeout=60)
            except Exception as e:
                last_exc = e
                logger.debug("Upload network error (attempt %d): %s", attempt + 1, e)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", self._retry_backoff))
                logger.debug("Upload 429 Rate limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                last_exc = None
                continue
            if resp.status_code >= 500 and attempt < self._max_retries:
                last_exc = None
                continue
            last_exc = None
            break

        if last_exc:
            raise MidjourneyError(
                f"Upload failed after {self._max_retries} retries: {last_exc}"
            ) from last_exc

        if resp is None:
            raise MidjourneyError("Upload failed: no response received")

        if resp.status_code >= 400:
            logger.debug("POST /api/storage-upload-file → %s", resp.status_code)
            logger.debug("Response: %s", resp.text[:500])
            resp.raise_for_status()

        data = resp.json()
        bucket_pathname = data["bucketPathname"]
        return f"{CDN_BASE}/{bucket_pathname}"

    def submit_job(
        self,
        params: BaseParams,
        mode: str = "fast",
        private: bool = False,
        metadata: dict | None = None,
    ) -> Job:
        """이미지 생성 작업을 제출합니다."""
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

        # 응답 형식: {"success": [{"job_id": "..."}], "failure": [...]}
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

    # -- 후처리 메서드 ------------------------------------------

    def _submit_postprocess(
        self,
        job_id: str,
        index: int,
        task_type: str,
        extra: dict,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """후처리 작업(vary/upscale/pan)을 제출합니다."""
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
        self,
        job_id: str,
        index: int,
        strong: bool = True,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Vary (Strong/Subtle) 작업을 제출합니다."""
        return self._submit_postprocess(
            job_id, index, "vary",
            extra={"strong": strong},
            mode=mode, private=private,
        )

    def submit_upscale(
        self,
        job_id: str,
        index: int,
        upscale_type: str = UpscaleType.SUBTLE,
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Upscale 작업을 제출합니다."""
        return self._submit_postprocess(
            job_id, index, "upscale",
            extra={"type": upscale_type},
            mode=mode, private=private,
        )

    def submit_pan(
        self,
        job_id: str,
        index: int,
        direction: str = "up",
        prompt: str = "",
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """Pan 작업을 제출합니다."""
        return self._submit_postprocess(
            job_id, index, "pan",
            extra={
                "direction": PanDirection[direction.upper()].value,
                "newPrompt": prompt,
                "fraction": 0.5,
                "stitch": True,
            },
            mode=mode, private=private,
        )

    # -- 애니메이션 메서드 ------------------------------------------------

    def _check_resolution(self, resolution: str) -> None:
        valid = {r.value for r in VideoResolution}
        if resolution not in valid:
            raise MidjourneyError(
                f"Unsupported video resolution '{resolution}'. "
                f"Must be one of: {sorted(valid)}"
            )

    def _video_payload(
        self,
        video_type: str,
        new_prompt: str,
        parent_job: dict | None,
        animate_mode: str,
        mode: str,
        private: bool,
    ) -> dict:
        """비디오 제출 공통 페이로드를 빌드합니다."""
        return {
            "t": "video",
            "videoType": video_type,
            "newPrompt": new_prompt,
            "parentJob": parent_job,
            "animateMode": animate_mode,
            "channelId": f"singleplayer_{self._auth.user_id}",
            "f": {"mode": mode, "private": private},
            "roomId": None,
            "metadata": {
                "isMobile": None, "imagePrompts": None,
                "imageReferences": None, "characterReferences": None,
                "depthReferences": None, "lightboxOpen": None,
            },
        }

    def _extract_video_job_id(self, data: Any) -> str:
        """/api/submit-jobs 비디오 응답에서 job_id를 추출합니다."""
        if isinstance(data, dict):
            success = data.get("success", [])
            if success:
                return success[0].get("job_id", "")
        return ""

    def submit_animate(
        self,
        job_id: str,
        index: int,
        prompt: str = "",
        end_url: str | None = None,
        motion: str | None = None,
        batch_size: int = 1,
        resolution: str = "480",
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """imagine 결과로부터 이미지-to-비디오 애니메이션 작업을 제출합니다.

        매개변수:
            job_id: 애니메이션할 완료된 imagine 작업 ID.
            index: 그리드 내 이미지 인덱스 (0-3).
            prompt: 선택적 추가 프롬프트 텍스트.
            end_url: 끝 프레임의 CDN URL. 제공 시
                     ``--end {url}``과 함께 ``vid_1.1_i2v_start_end``를 사용합니다.
            motion: 모션 강도 ("low" 또는 "high").
            batch_size: 생성할 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            private: 작업을 비공개(스텔스)로 설정할지 여부.
        """
        self._check_resolution(resolution)
        parts = []
        if prompt:
            parts.append(prompt)
        parts.append(f"--bs {batch_size}")
        if motion:
            parts.append(f"--motion {motion}")
        parts.append("--video 1")

        if end_url:
            parts.append(f"--end {end_url}")
            video_type = f"vid_1.1_i2v_start_end_{resolution}"
            animate_mode = "manual"
            event_type = "video_start_end"
        else:
            video_type = f"vid_1.1_i2v_{resolution}"
            animate_mode = "auto"
            event_type = "video_diffusion"

        full_prompt = " ".join(parts)
        payload = self._video_payload(
            video_type=video_type,
            new_prompt=full_prompt,
            parent_job={"job_id": job_id, "image_num": index},
            animate_mode=animate_mode,
            mode=mode,
            private=private,
        )
        data = self._request("POST", "/api/submit-jobs", json=payload)
        return Job(
            id=self._extract_video_job_id(data),
            prompt=full_prompt,
            status="pending",
            user_id=self._auth.user_id,
            parent_id=job_id,
            event_type=event_type,
        )

    def submit_animate_from_image(
        self,
        start_url: str,
        end_url: str | None = None,
        prompt: str = "",
        motion: str | None = None,
        batch_size: int = 1,
        resolution: str = "480",
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """이미지 파일로부터 애니메이션 작업을 제출합니다.

        모드:
        - 단일 이미지 (end_url=None):  ``vid_1.1_i2v_{res}``, ``animateMode=manual``
        - 시작+끝 (end_url=<url>):     ``vid_1.1_i2v_start_end_{res}``
        - 시작+루프 (end_url="loop"):  ``vid_1.1_i2v_start_end_{res}``, ``--motion {motion}``

        매개변수:
            start_url: 시작 프레임 이미지의 CDN URL.
            end_url: 끝 프레임의 CDN URL, 루프는 "loop", 단일 이미지 모드는 None.
            prompt: 선택적 텍스트 프롬프트.
            motion: 모션 강도 ("low" 또는 "high"). end_url="loop"일 때 사용.
            batch_size: 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            private: 작업을 비공개로 설정할지 여부.
        """
        self._check_resolution(resolution)

        parts = [start_url]
        if prompt:
            parts.append(prompt)
        parts.append(f"--bs {batch_size}")
        if end_url is None:
            parts.append("--video 1")
            video_type = f"vid_1.1_i2v_{resolution}"
            animate_mode = "manual"
            parent_job = None
            event_type = "video_diffusion"
        else:
            if motion:
                parts.append(f"--motion {motion}")
            parts.append("--video 1")
            parts.append(f"--end {end_url}")
            video_type = f"vid_1.1_i2v_start_end_{resolution}"
            animate_mode = "manual"
            parent_job = None
            event_type = "video_start_end"
        full_prompt = " ".join(parts)

        payload = self._video_payload(
            video_type=video_type,
            new_prompt=full_prompt,
            parent_job=parent_job,
            animate_mode=animate_mode,
            mode=mode,
            private=private,
        )
        data = self._request("POST", "/api/submit-jobs", json=payload)
        return Job(
            id=self._extract_video_job_id(data),
            prompt=full_prompt,
            status="pending",
            user_id=self._auth.user_id,
            event_type=event_type,
        )

    def submit_extend_video(
        self,
        job_id: str,
        index: int = 0,
        prompt: str = "",
        end_url: str | None = None,
        motion: str | None = None,
        batch_size: int = 1,
        resolution: str = "480",
        mode: str = "fast",
        private: bool = False,
    ) -> Job:
        """기존 비디오 작업을 연장합니다.

        end_url에 따른 두 가지 모드:
        - ``end_url=None``:   ``vid_1.1_i2v_extend`` (비디오 길이 연장)
        - ``end_url="loop"``: ``vid_1.1_i2v_start_end`` + ``--end loop``
        - ``end_url=<url>``:  ``vid_1.1_i2v_start_end`` + ``--end {url}``

        매개변수:
            job_id: 연장할 완료된 비디오 작업 ID.
            index: 연장할 배치 변형 인덱스 (기본값 0).
            prompt: 선택적 추가 프롬프트 텍스트.
            end_url: 끝 프레임 URL, 매끄러운 루프는 "loop", 단순 연장은 None.
            motion: 모션 강도 ("low" 또는 "high").
            batch_size: 비디오 변형 수 (``--bs N``). 기본값 1.
            resolution: 비디오 해상도 ('480' 또는 '720').
            mode: 속도 모드 ('fast', 'relax', 'turbo').
            private: 작업을 비공개로 설정할지 여부.
        """
        self._check_resolution(resolution)

        if end_url:
            parts = []
            if prompt:
                parts.append(prompt)
            parts.append(f"--bs {batch_size}")
            if motion:
                parts.append(f"--motion {motion}")
            parts.append("--video 1")
            parts.append(f"--end {end_url}")
            full_prompt = " ".join(parts)
            payload = self._video_payload(
                video_type=f"vid_1.1_i2v_start_end_{resolution}",
                new_prompt=full_prompt,
                parent_job={"job_id": job_id, "image_num": index},
                animate_mode="manual",
                mode=mode,
                private=private,
            )
            event_type = "video_start_end"
        else:
            parts = []
            if prompt:
                parts.append(prompt)
            parts.append(f"--bs {batch_size}")
            if motion:
                parts.append(f"--motion {motion}")
            parts.append("--video 1")
            full_prompt = " ".join(parts)
            payload = self._video_payload(
                video_type=f"vid_1.1_i2v_extend_{resolution}",
                new_prompt=full_prompt,
                parent_job={"job_id": job_id, "image_num": index},
                animate_mode="auto",
                mode=mode,
                private=private,
            )
            event_type = "video_extended"

        data = self._request("POST", "/api/submit-jobs", json=payload)
        return Job(
            id=self._extract_video_job_id(data),
            prompt=full_prompt,
            status="pending",
            user_id=self._auth.user_id,
            parent_id=job_id,
            event_type=event_type,
        )

    # -- 작업 상태 및 목록 조회 ----------------------------------------------

    def get_job_status(self, job_id: str) -> Job | None:
        """imagine 목록에 작업이 존재하는지 확인합니다 (= 완료 여부 확인)."""
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
                    event_type=item.get("event_type"),
                )
        return None

    def get_imagine_list(self, page_size: int = 1000) -> list[Job]:
        """생성된 이미지 전체 목록을 가져옵니다."""
        user_id = self._auth.user_id
        data = self._request(
            "GET", "/api/imagine",
            params={"user_id": user_id, "page_size": page_size},
        )
        return self._parse_jobs(data)

    def get_user_queue(self) -> dict:
        """현재 사용자의 작업 큐 상태를 가져옵니다."""
        return self._request("GET", "/api/user-queue")

    def get_user_state(self) -> UserSettings:
        """현재 사용자의 변경 가능한 설정을 가져옵니다."""
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
        """API 응답을 Job 객체 목록으로 파싱합니다."""
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
                event_type=item.get("event_type"),
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
