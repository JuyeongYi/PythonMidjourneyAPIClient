# Midjourney Python API Client

## Claude Code 규칙

- **`uv run python` 금지** — WSL 환경에서 Windows `.venv`를 덮어쓰므로 절대 사용하지 말 것
- 테스트는 사용자가 Windows에서 직접 실행 — WSL에서 `.venv` 건드리지 말 것
- 코드 검증은 `Grep`, `Read` 도구로 정적 확인만 수행

Unofficial Python client for the Midjourney image generation API, reverse-engineered from midjourney.com.

## Setup

```bash
uv sync                        # install all dependencies
playwright install chromium    # install browser for login
```

## Commands

```bash
uv run midjourney login                              # Browser OAuth login
uv run midjourney imagine "prompt" --ar 16:9         # Generate images
uv run midjourney imagine "prompt" --image ./ref.png # Image prompt (upload)
uv run midjourney imagine "prompt" --sref ./s.png    # Style reference (upload)
uv run midjourney imagine "prompt" --oref ./c.png    # Object reference (upload)
uv run midjourney vary <job_id> <index> [--subtle]                     # Vary (Strong/Subtle)
uv run midjourney upscale <job_id> <index> [--type]                    # Upscale (subtle/creative)
uv run midjourney pan <job_id> <index> -d up                           # Pan (up/down/left/right)
uv run midjourney animate <job_id> <index>                             # Animate from imagine grid
uv run midjourney animate-from-image ./start.png                       # Animate: start only
uv run midjourney animate-from-image ./start.png ./end.png             # Animate: start+end
uv run midjourney animate-from-image ./start.png --end-image loop --motion high  # Animate: start+loop
uv run midjourney extend-video <job_id> --motion low                   # Extend video
uv run midjourney extend-video <job_id> --end-image ./frame.png        # Extend with end frame (start_end type)
uv run midjourney extend-video <job_id> --end-image loop               # Loop version
uv run midjourney download-video <job_id> [--size 1080]                # Download video
uv run midjourney list                                                 # List recent jobs
uv run midjourney download <job_id>                                    # Download images
```

## Architecture

- `midjourney_api/client.py` — High-level API (`MidjourneyClient`): imagine, vary, upscale, pan, animate, animate_from_image, extend_video, download
- `midjourney_api/api.py` — Low-level REST API wrapper (`upload_image`, `submit_job`, `submit_vary`, `submit_upscale`, `submit_pan`, `submit_animate`, `submit_animate_from_image`, `submit_extend_video`)
- `midjourney_api/auth.py` — Firebase Auth / token refresh / Playwright browser login
- `midjourney_api/models.py` — Dataclass models (`Job`, `UserSettings`)
- `midjourney_api/params/types.py` — Custom types (`MJParam`, `_RangeInt`, `_Flag`, `_ModeEnum`, `SpeedMode`, `VisibilityMode`)
- `midjourney_api/params/v7.py` — V7 parameter set with cross-field validation
- `midjourney_api/params/__init__.py` — `create_params()` factory (raw value → typed instance casting)
- `midjourney_api/params/base.py` — `BaseParams` ABC
- `midjourney_api/exceptions.py` — Custom exceptions (`MidjourneyError`, `AuthenticationError`, `ValidationError`)
- `midjourney_api/cli.py` — CLI entry point (`pyproject.toml` → `midjourney_api.cli:main`)

## Conventions

- Sync-first (`curl_cffi` with Chrome TLS impersonation to bypass Cloudflare)
- `MidjourneyClient(print_log=False)` — set `print_log=True` to enable progress logs; `api.py` uses `logging.getLogger(__name__)` for debug output (HTTP errors), enabled via `logging.basicConfig(level=logging.DEBUG)`
- Parameters are appended to prompt strings (e.g., `prompt --ar 16:9 --s 200`)
- Authentication via Firebase refresh token in `.env`
- All API calls require `x-csrf-protection: 1` header
- Cookie name: `__Host-Midjourney.AuthUserTokenV3_i` (ID token)
- All postprocess operations (vary/upscale/pan) share `/api/submit-jobs` endpoint, differentiated by `t` field
- Upscale is terminal — cannot pan/vary an upscaled result; must branch from a grid job
- Image upload: `POST /api/storage-upload-file` (multipart) → CDN URL `https://cdn.midjourney.com/u/{bucketPathname}`
- All 3 image reference types share the same upload flow: image prompt, sref, oref
- `oref` accepts image files/URLs only (no codes); `sref` accepts codes, URLs, and files
- Reference+weight pairs: image+`--iw`(0-3, default 1), sref+`--sw`(0-1000, default 100), oref+`--ow`(1-1000, default 100)
- `-p`/`--personalize`: code string (UUID-like) or empty string (default profile)
- Niji (`--niji N`): incompatible with oref, tile, quality
- Download: based on `job.image_urls` length (grid=4 images, upscale=1 image)
- Output path: `{output_dir}/{job_id}_{index}.webp`
- `download_images_bytes(job, size, indices)` — returns `list[bytes]` without disk I/O (for PIL/BytesIO processing)
- Animation video types: `vid_1.1_i2v_{res}` (i2v), `vid_1.1_i2v_start_end_{res}` (start/end/loop), `vid_1.1_i2v_extend_{res}` (extend)
- Video CDN: `cdn.midjourney.com/video/{job_id}/0.mp4` (raw), `0_{size}_N.mp4` (social), `0_N.gif` (gif)
- `animate(job_id, index, motion, stealth)` — i2v from imagine grid; supports motion low/high, stealth
- `animate_from_image(start, end_image, motion, stealth, batch_size)` — 3 modes: start-only / start+end_image / start+end_image="loop"
- `extend_video(job_id, index, end_image, motion, stealth, batch_size)` — extend video; `end_image` → `vid_1.1_i2v_start_end` (file/URL auto-uploaded, `"loop"` passed as-is)
- `download_video(job, output_dir, size, batch_size)` → `list[Path]`; filename: `{job_id}_{index}.mp4`; `download_video_bytes(job, size, batch_size)` → `list[bytes]`
- CLI `--verbose/-v`: global flag controlling `print_log`; job IDs always printed regardless
- `MidjourneyClient(max_retries=3, retry_backoff=2.0)` — retries on network errors, 5xx, and 429 (respects Retry-After)

## Type System

- All parameters are custom types inheriting from primitives (`int`, `str`, `float`)
- Range validation at construction time; `to_prompt(version)` generates a prompt fragment
- `SpeedMode`/`VisibilityMode` are `_ModeEnum(StrEnum)` — mutual exclusivity structurally enforced
- Two parameter construction patterns: `create_params()` (auto-casting raw values) vs `V7Params()` (typed instances directly)

## Dependencies

- `curl_cffi>=0.7` — HTTP client (Chrome TLS fingerprint)
- `python-dotenv>=1.0` — .env loading
- `httpx>=0.28` — Firebase token refresh
- `playwright>=1.40` — Browser-based login (required dependency)
