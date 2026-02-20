# Feature Additions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add retry/fault tolerance and animation (video generation) to the midjourney_api library.

**Architecture:** Retry logic wraps `MidjourneyAPI._request()` transparently. Animation adds two new submit methods to `api.py`, two new client methods to `client.py`, three new Job model methods, and two CLI subcommands.

**Tech Stack:** Python 3.11+, curl_cffi, existing `_submit_postprocess()` pattern in `api.py`

**Design doc:** `docs/plans/2026-02-21-feature-additions-design.md`

---

## Task 1: Retry logic in `MidjourneyAPI`

**Files:**
- Modify: `midjourney_api/api.py:34-36` (`__init__`), `midjourney_api/api.py:41-71` (`_request`)
- Modify: `midjourney_api/client.py:27-35` (`__init__`)

### Step 1: Add `max_retries` / `retry_backoff` to `MidjourneyAPI.__init__`

In `api.py`, change `__init__`:

```python
def __init__(self, auth: MidjourneyAuth, max_retries: int = 3, retry_backoff: float = 2.0):
    self._auth = auth
    self._session = curl_requests.Session(impersonate="chrome")
    self._max_retries = max_retries
    self._retry_backoff = retry_backoff
```

### Step 2: Add retry loop to `_request()`

Replace the `resp = self._session.request(...)` block (lines 62–71) with:

```python
import time as _time
from curl_cffi import CurlError

last_exc: Exception | None = None
for attempt in range(self._max_retries + 1):
    if attempt > 0:
        wait = self._retry_backoff * (2 ** (attempt - 1))
        logger.debug("Retry %d/%d after %.1fs", attempt, self._max_retries, wait)
        _time.sleep(wait)
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
        _time.sleep(retry_after)
        last_exc = None
        continue
    if resp.status_code >= 500:
        last_exc = None
        if attempt < self._max_retries:
            continue
    break
else:
    if last_exc:
        raise MidjourneyError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc

if last_exc:
    raise MidjourneyError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc

if resp.status_code >= 400:
    cookie_hdr = self._auth.cookie_header()
    logger.debug("%s %s → %s", method, path, resp.status_code)
    logger.debug("Cookie: %s...(%d chars)", cookie_hdr[:80], len(cookie_hdr))
    logger.debug("User ID: %s", self._auth.user_id)
    logger.debug("Response: %s", resp.text[:500])
    resp.raise_for_status()
return resp.json() if resp.content else None
```

Also add `import time as _time` at the top of the file (or move to module level — use `import time` module-level).

### Step 3: Propagate params through `MidjourneyClient.__init__`

In `client.py`, change `__init__`:

```python
def __init__(
    self,
    refresh_token: str | None = None,
    env_path: str = ".env",
    print_log: bool = False,
    max_retries: int = 3,
    retry_backoff: float = 2.0,
):
    self._auth = MidjourneyAuth(refresh_token=refresh_token, env_path=env_path)
    self._api = MidjourneyAPI(self._auth, max_retries=max_retries, retry_backoff=retry_backoff)
    self._print_log = print_log
```

Also update `login()` to re-create `_api` with the same retry params:

```python
def login(self, force: bool = False) -> None:
    ...
    self._auth.login(force=force)
    self._api.close()
    self._api = MidjourneyAPI(self._auth, max_retries=..., retry_backoff=...)
```

Store them as `self._max_retries` and `self._retry_backoff` for reuse.

### Step 4: Commit

```bash
git add midjourney_api/api.py midjourney_api/client.py
git commit -m "feat: add retry logic with exponential backoff to _request()"
```

---

## Task 2: Animation — `Job` model additions

**Files:**
- Modify: `midjourney_api/models.py`

### Step 1: Add `event_type` field and video URL methods

In `Job` dataclass, add field after `parent_id`:

```python
event_type: Optional[str] = None
```

Add methods after `cdn_url()`:

```python
@property
def is_video(self) -> bool:
    """True if this job is a video/animation job."""
    return "video" in (self.event_type or "")

def video_url(self, index: int = 0, size: int | None = None) -> str:
    """Build CDN URL for a video file.

    Args:
        index: Batch index (always 0 for batch_size=1).
        size: Resolution (e.g. 1080 for social). None = raw original.
    """
    if size:
        return f"https://cdn.midjourney.com/video/{self.id}/{index}_{size}_N.mp4"
    return f"https://cdn.midjourney.com/video/{self.id}/{index}.mp4"

def gif_url(self, index: int = 0) -> str:
    """Build CDN URL for a GIF version of a video job."""
    return f"https://cdn.midjourney.com/video/{self.id}/{index}_N.gif"
```

### Step 2: Update `_parse_jobs()` in `api.py` to populate `event_type`

In `api.py`, `_parse_jobs()` method, update the `Job(...)` constructor call to include:

```python
job = Job(
    id=item.get("id", item.get("job_id", "")),
    prompt=item.get("prompt", item.get("full_command", "")),
    status=self._normalize_status(item.get("current_status", item.get("status", "completed"))),
    progress=item.get("percentage_complete", 100),
    user_id=item.get("user_id", ""),
    enqueue_time=item.get("enqueue_time"),
    event_type=item.get("event_type"),
)
```

Note: video jobs in `/api/imagine` have no `current_status` field — they're always completed when they appear. Default to `"completed"`.

Also update `get_job_status()` similarly — add `event_type=item.get("event_type")` to the `Job(...)` call there.

### Step 3: Commit

```bash
git add midjourney_api/models.py midjourney_api/api.py
git commit -m "feat: add event_type field and video_url/gif_url methods to Job"
```

---

## Task 3: Animation — `api.py` submit methods

**Files:**
- Modify: `midjourney_api/api.py` (add after `submit_pan`)

### Step 1: Add `submit_animate()` (i2v from imagine)

Add after the `submit_pan` method:

```python
# -- Animation methods ------------------------------------------------

def submit_animate(
    self,
    job_id: str,
    index: int,
    prompt: str = "",
    resolution: str = "480",
    mode: str = "fast",
    private: bool = False,
) -> Job:
    """Submit an Image-to-Video animation job from an imagine result.

    Args:
        job_id: Completed imagine job ID to animate.
        index: Image index within the grid (0-3).
        prompt: Optional additional prompt text.
        resolution: Video resolution ('480'). Future: '720'.
        mode: Speed mode ('fast', 'relax', 'turbo').
        private: Whether to make the job private.
    """
    user_id = self._auth.user_id
    payload = {
        "t": "video",
        "videoType": f"vid_1.1_i2v_{resolution}",
        "newPrompt": prompt,
        "parentJob": {"job_id": job_id, "image_num": index},
        "animateMode": "auto",
        "channelId": f"singleplayer_{user_id}",
        "f": {"mode": mode, "private": private},
        "roomId": None,
        "metadata": {
            "isMobile": None, "imagePrompts": None,
            "imageReferences": None, "characterReferences": None,
            "depthReferences": None, "lightboxOpen": None,
        },
    }
    data = self._request("POST", "/api/submit-jobs", json=payload)

    job_id_new = ""
    if isinstance(data, dict):
        success = data.get("success", [])
        if success:
            job_id_new = success[0].get("job_id", "")

    return Job(
        id=job_id_new,
        prompt=prompt,
        status="pending",
        user_id=user_id,
        parent_id=job_id,
        event_type="video_diffusion",
    )
```

### Step 2: Add `submit_animate_from_image()` (start only / start+end / start+loop)

Add after `submit_animate`:

```python
def submit_animate_from_image(
    self,
    start_url: str,
    end_url: str | None = None,
    motion: str | None = None,
    prompt: str = "",
    resolution: str = "480",
    mode: str = "fast",
    private: bool = False,
) -> Job:
    """Submit an animation from image files.

    Three modes depending on end_url and motion:
    - start only:   end_url=None, motion=None  → ``{start_url} --bs 1 --video 1``
    - start+end:    end_url=<url>, motion=None → ``{start_url} --bs 1 --video 1 --end {end_url}``
    - start+loop:   end_url="loop", motion=low|high → ``{start_url} --bs 1 --motion {motion} --video 1 --end loop``

    Args:
        start_url: CDN URL of the start frame image.
        end_url: CDN URL of end frame, "loop" for looping, or None for start-only.
        motion: Motion intensity ("low" or "high"). Required for loop mode.
        prompt: Optional text prompt.
        resolution: Video resolution ('480'). Future: '720'.
        mode: Speed mode ('fast', 'relax', 'turbo').
        private: Whether to make the job private.
    """
    user_id = self._auth.user_id

    parts = [start_url]
    if prompt:
        parts.append(prompt)
    parts.append("--bs 1")
    if motion and end_url == "loop":
        parts.append(f"--motion {motion}")
    parts.append("--video 1")
    if end_url:
        parts.append(f"--end {end_url}")
    full_prompt = " ".join(parts)

    payload = {
        "t": "video",
        "videoType": f"vid_1.1_i2v_start_end_{resolution}",
        "newPrompt": full_prompt,
        "parentJob": None,
        "animateMode": "manual",
        "channelId": f"singleplayer_{user_id}",
        "f": {"mode": mode, "private": private},
        "roomId": None,
        "metadata": {
            "isMobile": None, "imagePrompts": None,
            "imageReferences": None, "characterReferences": None,
            "depthReferences": None, "lightboxOpen": None,
        },
    }
    data = self._request("POST", "/api/submit-jobs", json=payload)

    job_id_new = ""
    if isinstance(data, dict):
        success = data.get("success", [])
        if success:
            job_id_new = success[0].get("job_id", "")

    return Job(
        id=job_id_new,
        prompt=full_prompt,
        status="pending",
        user_id=user_id,
        event_type="video_start_end",
    )
```

### Step 3: Add `submit_extend_video()` (extend from existing video job)

Add after `submit_animate_from_image`:

```python
def submit_extend_video(
    self,
    job_id: str,
    motion: str | None = None,
    resolution: str = "480",
    mode: str = "fast",
    private: bool = False,
) -> Job:
    """Extend an existing video job.

    Args:
        job_id: Completed video job ID to extend.
        motion: Motion intensity ("low" or "high").
        resolution: Video resolution ('480'). Future: '720'.
        mode: Speed mode ('fast', 'relax', 'turbo').
        private: Whether to make the job private.
    """
    user_id = self._auth.user_id

    parts = ["--bs 1"]
    if motion:
        parts.append(f"--motion {motion}")
    parts.append("--video 1")
    full_prompt = " ".join(parts)

    payload = {
        "t": "video",
        "videoType": f"vid_1.1_i2v_extend_{resolution}",
        "newPrompt": full_prompt,
        "parentJob": {"job_id": job_id, "image_num": 0},
        "animateMode": "auto",
        "channelId": f"singleplayer_{user_id}",
        "f": {"mode": mode, "private": private},
        "roomId": None,
        "metadata": {
            "isMobile": None, "imagePrompts": None,
            "imageReferences": None, "characterReferences": None,
            "depthReferences": None, "lightboxOpen": None,
        },
    }
    data = self._request("POST", "/api/submit-jobs", json=payload)

    job_id_new = ""
    if isinstance(data, dict):
        success = data.get("success", [])
        if success:
            job_id_new = success[0].get("job_id", "")

    return Job(
        id=job_id_new,
        prompt=full_prompt,
        status="pending",
        user_id=user_id,
        parent_id=job_id,
        event_type="video_extended",
    )
```

### Step 4: Commit

```bash
git add midjourney_api/api.py
git commit -m "feat: add submit_animate, submit_animate_from_image, submit_extend_video to MidjourneyAPI"
```

---

## Task 4: Animation — `client.py` high-level methods + download

**Files:**
- Modify: `midjourney_api/client.py` (add after `pan`, before `download_images`)

### Step 1: Add `animate()`

```python
def animate(
    self,
    job_id: str,
    index: int,
    *,
    prompt: str = "",
    resolution: str = "480",
    wait: bool = True,
    poll_interval: float = 5,
    timeout: float = 600,
    mode: str = "fast",
) -> Job:
    """Generate an animation from a completed imagine job.

    Args:
        job_id: Completed imagine job ID.
        index: Image index within the grid (0-3).
        prompt: Optional additional prompt text.
        resolution: Video resolution ('480').
        wait: If True, poll until the job completes.
        poll_interval: Seconds between status polls.
        timeout: Maximum seconds to wait.
        mode: Speed mode ('fast', 'relax', 'turbo').

    Returns:
        Completed Job with video_url()/gif_url() available.
    """
    job = self._api.submit_animate(
        job_id, index, prompt=prompt, resolution=resolution, mode=mode,
    )
    self._log(f"Animate submitted: {job.id}")

    if not wait:
        return job
    return self._poll_job(job.id, poll_interval, timeout)
```

### Step 2: Add `animate_from_image()`

Covers three modes: start only (`end_image=None`), start+end, and start+loop (`end_image="loop"`).
For loop mode, `motion` is required. For start only / start+end, `motion` is ignored.

```python
def animate_from_image(
    self,
    start_image: str,
    end_image: str | None = None,
    *,
    motion: str | None = None,
    prompt: str = "",
    resolution: str = "480",
    wait: bool = True,
    poll_interval: float = 5,
    timeout: float = 600,
    mode: str = "fast",
) -> Job:
    """Generate an animation from image files.

    Modes:
    - Start only:   end_image=None
    - Start+end:    end_image=<local file or URL>
    - Start+loop:   end_image="loop", motion="low"|"high"

    Args:
        start_image: Local file or URL for the start frame (auto-uploaded if local).
        end_image: Local file/URL for end frame, "loop" for loop mode, or None.
        motion: Motion intensity ("low" or "high"). Required when end_image="loop".
        prompt: Optional text prompt.
        resolution: Video resolution ('480').
        wait: If True, poll until the job completes.
        poll_interval: Seconds between status polls.
        timeout: Maximum seconds to wait.
        mode: Speed mode ('fast', 'relax', 'turbo').

    Returns:
        Completed Job with video_url()/gif_url() available.
    """
    start_url = self._upload_if_local(start_image)
    # "loop" is a sentinel value, not a file path — pass through as-is
    end_url: str | None
    if end_image is None or end_image == "loop":
        end_url = end_image  # None or "loop"
    else:
        end_url = self._upload_if_local(end_image)

    job = self._api.submit_animate_from_image(
        start_url, end_url=end_url, motion=motion,
        prompt=prompt, resolution=resolution, mode=mode,
    )
    self._log(f"Animate from image submitted: {job.id}")

    if not wait:
        return job
    return self._poll_job(job.id, poll_interval, timeout)
```

### Step 3: Add `extend_video()`

```python
def extend_video(
    self,
    job_id: str,
    *,
    motion: str | None = None,
    resolution: str = "480",
    wait: bool = True,
    poll_interval: float = 5,
    timeout: float = 600,
    mode: str = "fast",
) -> Job:
    """Extend a completed video job.

    Args:
        job_id: Completed video job ID to extend.
        motion: Motion intensity ("low" or "high").
        resolution: Video resolution ('480').
        wait: If True, poll until the job completes.
        poll_interval: Seconds between status polls.
        timeout: Maximum seconds to wait.
        mode: Speed mode ('fast', 'relax', 'turbo').

    Returns:
        Completed Job with video_url()/gif_url() available.
    """
    job = self._api.submit_extend_video(
        job_id, motion=motion, resolution=resolution, mode=mode,
    )
    self._log(f"Extend video submitted: {job.id}")

    if not wait:
        return job
    return self._poll_job(job.id, poll_interval, timeout)
```

### Step 4: Add `download_video()` and `download_video_bytes()`

Add after `download_images_bytes`:

```python
def download_video(
    self,
    job: Job,
    output_dir: str = "./videos",
    size: int | None = None,
) -> Path:
    """Download a completed animation video to disk.

    Args:
        job: Completed video Job.
        output_dir: Directory to save the video.
        size: Resolution (e.g. 1080 for social). None = raw original.

    Returns:
        Path to the saved .mp4 file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    url = job.video_url(size=size)
    suffix = f"_{size}" if size else ""
    file_path = out / f"{job.id}{suffix}.mp4"

    self._log(f"Downloading video...")
    resp = curl_requests.get(url, timeout=120, impersonate="chrome")
    resp.raise_for_status()
    with open(file_path, "wb") as f:
        f.write(resp.content)

    self._log(f"  Saved: {file_path}")
    return file_path

def download_video_bytes(
    self,
    job: Job,
    size: int | None = None,
) -> bytes:
    """Download a completed animation video as raw bytes (no disk I/O).

    Args:
        job: Completed video Job.
        size: Resolution (e.g. 1080 for social). None = raw original.

    Returns:
        Raw MP4 bytes.
    """
    url = job.video_url(size=size)
    resp = curl_requests.get(url, timeout=120, impersonate="chrome")
    resp.raise_for_status()
    return resp.content
```

### Step 4: Commit

```bash
git add midjourney_api/client.py
git commit -m "feat: add animate, animate_between, download_video to MidjourneyClient"
```

---

## Task 5: Animation — CLI subcommands

**Files:**
- Modify: `midjourney_api/cli.py`

### Step 1: Add `cmd_animate()` handler

After `cmd_pan` function, add:

```python
def cmd_animate(args: argparse.Namespace) -> None:
    """Handle the animate command (i2v from imagine)."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=True) as client:
        job = client.animate(
            args.job_id,
            args.index,
            prompt=args.prompt,
            resolution=args.resolution,
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        path = client.download_video(job, output_dir=args.output, size=args.size)
        print(f"Saved: {path}")


def cmd_animate_from_image(args: argparse.Namespace) -> None:
    """Handle the animate-from-image command (start / start+end / start+loop)."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=True) as client:
        job = client.animate_from_image(
            args.start_image,
            args.end_image,   # None, "loop", or file/URL
            motion=args.motion,
            prompt=args.prompt,
            resolution=args.resolution,
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        path = client.download_video(job, output_dir=args.output, size=args.size)
        print(f"Saved: {path}")


def cmd_extend_video(args: argparse.Namespace) -> None:
    """Handle the extend-video command."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=True) as client:
        job = client.extend_video(
            args.job_id,
            motion=args.motion,
            resolution=args.resolution,
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        path = client.download_video(job, output_dir=args.output, size=args.size)
        print(f"Saved: {path}")
```

### Step 2: Register subcommands in `main()`

After the `pan` subcommand block, add:

```python
# animate (i2v from imagine)
p_animate = sub.add_parser("animate", help="Generate animation from an imagine job")
p_animate.add_argument("job_id", help="Source imagine job ID")
p_animate.add_argument("index", type=int, help="Image index (0-3)")
p_animate.add_argument("-p", "--prompt", default="", help="Additional prompt text")
p_animate.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
p_animate.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
p_animate.add_argument("-o", "--output", default="./videos", help="Output directory")
p_animate.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

# animate-from-image (start / start+end / start+loop)
p_afi = sub.add_parser("animate-from-image", help="Generate animation from image files")
p_afi.add_argument("start_image", help="Start frame (local file or URL)")
p_afi.add_argument("end_image", nargs="?", default=None,
                   help="End frame (local file or URL), 'loop' for looping, or omit for start-only")
p_afi.add_argument("--motion", choices=["low", "high"], default=None,
                   help="Motion intensity (required for loop mode)")
p_afi.add_argument("-p", "--prompt", default="", help="Text prompt")
p_afi.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
p_afi.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
p_afi.add_argument("-o", "--output", default="./videos", help="Output directory")
p_afi.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

# extend-video
p_ext = sub.add_parser("extend-video", help="Extend an existing video job")
p_ext.add_argument("job_id", help="Source video job ID")
p_ext.add_argument("--motion", choices=["low", "high"], default=None,
                   help="Motion intensity (low or high)")
p_ext.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
p_ext.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
p_ext.add_argument("-o", "--output", default="./videos", help="Output directory")
p_ext.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")
```

Also add to the command dispatch dict:

```python
"animate": cmd_animate,
"animate-from-image": cmd_animate_from_image,
"extend-video": cmd_extend_video,
```

### Step 3: Commit

```bash
git add midjourney_api/cli.py
git commit -m "feat: add animate, animate-from-image, extend-video CLI subcommands"
```

---

## Task 6: Docs update

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `README.en.md`

### Step 1: Update `CLAUDE.md` Conventions section

Add to the Conventions bullet list:

```markdown
- `animate(job_id, index)` — Image-to-Video; `animate_between(start, end)` — start+end frame video
- Video CDN: `cdn.midjourney.com/video/{job_id}/{index}.mp4` (raw), `{index}_{size}_N.mp4` (sized), `{index}_N.gif`
- `videoType` format: `vid_1.1_i2v_{resolution}` (i2v) / `vid_1.1_i2v_start_end_{resolution}` (start+end)
- Retry: `MidjourneyClient(max_retries=3, retry_backoff=2.0)` — retries on 5xx and network errors
```

Also add to the Commands section:

```markdown
uv run midjourney animate <job_id> <index>               # Image-to-Video
uv run midjourney animate-between ./start.png ./end.png  # Start+end frame video
uv run midjourney download-video <job_id> [--size 1080]  # Download video
```

### Step 2: Update README.md and README.en.md

Add new sections for animate/animate_between Python usage and CLI, similar to existing vary/upscale/pan sections.

### Step 3: Commit

```bash
git add CLAUDE.md README.md README.en.md
git commit -m "docs: update docs for retry and animation features"
```

---

## Task 7: Final push

```bash
git push
```
