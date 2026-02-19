# Midjourney Python API Client

Unofficial Python client for the Midjourney image generation API, reverse-engineered from midjourney.com.

## Commands

```bash
uv run midjourney login                              # Browser OAuth login
uv run midjourney imagine "prompt" --ar 16:9         # Generate images
uv run midjourney imagine "prompt" --image ./ref.png # Image prompt (upload)
uv run midjourney imagine "prompt" --sref ./s.png    # Style reference (upload)
uv run midjourney imagine "prompt" --oref ./c.png    # Object reference (upload)
uv run midjourney vary <job_id> <index> [--subtle]   # Vary (Strong/Subtle)
uv run midjourney upscale <job_id> <index> [--type]  # Upscale (subtle/creative)
uv run midjourney pan <job_id> <index> -d up         # Pan (up/down/left/right)
uv run midjourney list                               # List recent jobs
uv run midjourney download <job_id>                  # Download images
```

## Architecture

- `midjourney_api/client.py` — High-level API (`MidjourneyClient`): imagine, vary, upscale, pan, download
- `midjourney_api/api.py` — Low-level REST API wrapper (`upload_image`, `submit_job`, `submit_vary`, `submit_upscale`, `submit_pan`)
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
- Parameters are appended to prompt strings (e.g., `prompt --ar 16:9 --s 200`)
- Authentication via Firebase refresh token in `.env`
- All API calls require `x-csrf-protection: 1` header
- Cookie name: `__Host-Midjourney.AuthUserTokenV3_i` (ID token)
- All postprocess operations (vary/upscale/pan) share `/api/submit-jobs` endpoint, differentiated by `t` field
- Upscale is terminal — upscale 결과에 pan/vary 불가, 반드시 grid job에서 분기해야 함
- Image upload: `POST /api/storage-upload-file` (multipart) → CDN URL `https://cdn.midjourney.com/u/{bucketPathname}`
- 3가지 이미지 참조 타입이 동일한 업로드 플로우 공유: image prompt, sref, oref
- oref는 이미지(파일/URL)만 지원, 코드 불가. sref는 코드/URL/파일 모두 가능
- 참조+가중치 쌍: image+`--iw`(0-3, 기본 1), sref+`--sw`(0-1000, 기본 100), oref+`--ow`(1-1000, 기본 100)
- `-p`/`--personalize`: 코드 문자열(UUID-like) 또는 빈값(기본 프로파일)
- Niji (`--niji N`): oref, tile, quality와 비호환
- Download: `job.image_urls` 길이 기준으로 다운로드 (grid=4장, upscale=1장)
- 출력 경로: `{output_dir}/{job_id}_{index}.webp`

## Type System

- 모든 파라미터는 기본 자료형(`int`, `str`, `float`)을 상속한 커스텀 타입
- 생성 시점에서 값 범위 검증, `to_prompt(version)` 메서드로 프롬프트 조각 생성
- `SpeedMode`/`VisibilityMode`는 `_ModeEnum(StrEnum)` 기반 — 상호 배제 구조적 보장
- 두 가지 파라미터 생성 방식: `create_params()` (raw값 자동 캐스팅) vs `V7Params()` (타입 인스턴스 직접 전달)

## Dependencies

- `curl_cffi>=0.7` — HTTP client (Chrome TLS fingerprint)
- `python-dotenv>=1.0` — .env loading
- `httpx>=0.28` — Firebase token refresh
- `playwright>=1.40` — Browser-based login (dev group, `uv sync` 시 자동 포함)
