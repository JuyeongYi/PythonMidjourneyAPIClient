# Midjourney Python API Client

Unofficial Python client for the Midjourney image generation API, reverse-engineered from midjourney.com.

## Commands

```bash
uv run midjourney login                              # Browser OAuth login
uv run midjourney imagine "prompt" --ar 16:9         # Generate images
uv run midjourney vary <job_id> <index> [--subtle]   # Vary (Strong/Subtle)
uv run midjourney upscale <job_id> <index> [--type]  # Upscale (subtle/creative)
uv run midjourney pan <job_id> <index> -d up         # Pan (up/down/left/right)
uv run midjourney list                               # List recent jobs
uv run midjourney download <job_id>                  # Download images
```

## Architecture

- `midjourney/client.py` — High-level API (`MidjourneyClient`): imagine, vary, upscale, pan
- `midjourney/api.py` — Low-level REST API wrapper (`submit_job`, `submit_vary`, `submit_upscale`, `submit_pan`)
- `midjourney/auth.py` — Firebase Auth / token refresh
- `midjourney/models.py` — Dataclass models (`Job`, `UserSettings`)
- `midjourney/params/` — Version-specific parameter classes (`BaseParams` ABC → `V7Params`)
- `midjourney/exceptions.py` — Custom exceptions
- `midjourney/cli.py` — CLI entry point (`pyproject.toml` → `midjourney.cli:main`)

## Conventions

- Sync-first (`curl_cffi` with Chrome TLS impersonation to bypass Cloudflare)
- Parameters are appended to prompt strings (e.g., `prompt --ar 16:9 --s 200`)
- Authentication via Firebase refresh token in `.env`
- All API calls require `x-csrf-protection: 1` header
- Cookie name: `__Host-Midjourney.AuthUserTokenV3_i` (ID token)
- All postprocess operations (vary/upscale/pan) share `/api/submit-jobs` endpoint, differentiated by `t` field
- Upscale is terminal — upscale 결과에 pan/vary 불가, 반드시 grid job에서 분기해야 함

## Dependencies

- `curl_cffi>=0.7` — HTTP client (Chrome TLS fingerprint)
- `python-dotenv>=1.0` — .env loading
- `playwright>=1.40` — Browser-based login (optional, `uv run --extra login`)
