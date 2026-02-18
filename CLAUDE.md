# Midjourney Python API Client

Unofficial Python client for the Midjourney image generation API, reverse-engineered from midjourney.com.

## Architecture

- `midjourney/client.py` — High-level API (`MidjourneyClient`)
- `midjourney/auth.py` — Firebase Auth / token refresh
- `midjourney/api.py` — Low-level REST API wrapper
- `midjourney/models.py` — Dataclass models (Job, UserSettings)
- `midjourney/params/` — Version-specific parameter classes (ABC → V7Params)
- `midjourney/exceptions.py` — Custom exceptions
- `cli.py` — CLI entry point

## Conventions

- Sync-first (httpx sync client)
- Parameters are appended to prompt strings (e.g., `prompt --ar 16:9 --s 200`)
- Authentication via Firebase refresh token in `.env`
- All API calls require `x-csrf-protection: 1` header
- Cookie name: `__Host-Midjourney.AuthUserTokenV3_i` (ID token)

## Dependencies

- `httpx>=0.28` — HTTP client
- `python-dotenv` — .env loading
- `playwright` — Browser-based login (optional)
