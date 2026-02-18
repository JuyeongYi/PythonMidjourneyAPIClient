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

- `midjourney_api/client.py` — High-level API (`MidjourneyClient`): imagine, vary, upscale, pan
- `midjourney_api/api.py` — Low-level REST API wrapper (`upload_image`, `submit_job`, `submit_vary`, `submit_upscale`, `submit_pan`)
- `midjourney_api/auth.py` — Firebase Auth / token refresh
- `midjourney_api/models.py` — Dataclass models (`Job`, `UserSettings`)
- `midjourney_api/params/` — Version-specific parameter classes (`BaseParams` ABC → `V7Params`)
- `midjourney_api/exceptions.py` — Custom exceptions
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

## Dependencies

- `curl_cffi>=0.7` — HTTP client (Chrome TLS fingerprint)
- `python-dotenv>=1.0` — .env loading
- `playwright>=1.40` — Browser-based login (optional, `uv run --extra login`)
