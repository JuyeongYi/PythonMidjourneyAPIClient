# Feature Additions Design

Date: 2026-02-21

## Scope

Three features for the `midjourney_api` Python library (external app/script integration use case):

1. Retry / fault tolerance
2. Animation (video generation)
3. ~~Batch + progress callback~~ — deferred (not needed by current users)

---

## 1. Retry / Fault Tolerance

### Parameters

```python
MidjourneyClient(
    max_retries: int = 3,
    retry_backoff: float = 2.0,
)
```

### Behavior

- Retry on: network errors, HTTP 5xx, HTTP 429
- No retry on: HTTP 4xx (except 429), `JobFailedError`
- Backoff: `retry_backoff * 2^attempt` seconds between retries
- On 429: respect `Retry-After` header if present

### Implementation

`MidjourneyAPI.__init__` accepts `max_retries` and `retry_backoff`.
`_request()` wraps the HTTP call in a retry loop.

---

## 2. Animation (Video Generation)

### API Surface — Confirmed from reverse engineering

**Submit endpoints** (`/api/submit-jobs`):

| Mode | `t` | `videoType` | `animateMode` | `parentJob` |
|------|-----|-------------|---------------|-------------|
| i2v (from imagine) | `"video"` | `"vid_1.1_i2v_{resolution}"` | `"auto"` | `{"job_id": ..., "image_num": index}` |
| start+end frames | `"video"` | `"vid_1.1_i2v_start_end_{resolution}"` | `"manual"` | `null` |

Resolution confirmed: `"480"`. Others possible (e.g. `"720"`).

**start+end prompt format:**
```
{start_url} {prompt} --bs 1 --video 1 --end {end_url}
```

**Completion detection:** Same as images — poll `/api/imagine` until job appears.

**Completed job fields** (from `/api/imagine` response):
```json
{
  "id": "...",
  "event_type": "video_diffusion" | "video_start_end" | "video_extended",
  "job_type": "vid_1.1_i2v_render_b_joint_video" | ...,
  "video_segments": [125],
  "width": 624,
  "height": 624
}
```

**CDN URL format** (confirmed):
```
Raw:    https://cdn.midjourney.com/video/{job_id}/0.mp4
Social: https://cdn.midjourney.com/video/{job_id}/0_1080_N.mp4
GIF:    https://cdn.midjourney.com/video/{job_id}/0_N.gif
```

### Job Model Changes

Add to `models.py`:

```python
@property
def is_video(self) -> bool:
    return "video" in (self.event_type or "")

def video_url(self, index: int = 0, size: int | None = None) -> str:
    if size:
        return f"https://cdn.midjourney.com/video/{self.id}/{index}_{size}_N.mp4"
    return f"https://cdn.midjourney.com/video/{self.id}/{index}.mp4"

def gif_url(self, index: int = 0) -> str:
    return f"https://cdn.midjourney.com/video/{self.id}/{index}_N.gif"
```

### Low-level API (`api.py`)

```python
def submit_animate(
    self,
    job_id: str,
    index: int,
    prompt: str = "",
    resolution: str = "480",
    mode: str = "fast",
    private: bool = False,
) -> Job: ...

def submit_animate_between(
    self,
    start_url: str,
    end_url: str,
    prompt: str = "",
    resolution: str = "480",
    mode: str = "fast",
    private: bool = False,
) -> Job: ...
```

### High-level API (`client.py`)

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
) -> Job: ...

def animate_between(
    self,
    start_image: str,   # local file or URL — auto-uploaded if local
    end_image: str,
    prompt: str = "",
    *,
    resolution: str = "480",
    wait: bool = True,
    poll_interval: float = 5,
    timeout: float = 600,
    mode: str = "fast",
) -> Job: ...

def download_video(
    self,
    job: Job,
    output_dir: str = "./videos",
    size: int | None = None,   # None=raw, 1080=social
) -> Path: ...

def download_video_bytes(
    self,
    job: Job,
    size: int | None = None,
) -> bytes: ...
```

### CLI

```bash
uv run midjourney animate <job_id> <index>           # i2v from imagine
uv run midjourney animate <job_id> <index> -p "prompt"
uv run midjourney animate-between ./start.png ./end.png -p "prompt"
uv run midjourney download-video <job_id> [--size 1080]
```

---

## Out of Scope

- Async support (not needed for current use case)
- Job persistence / caching
- Rate limiter
- Video "extend" operation (new feature discovered: `event_type: video_extended`) — defer
