# Midjourney Python API Client

Unofficial Python API client for the Midjourney website. Generate and download images programmatically.

> **Warning**: This uses an unofficial API and may stop working if Midjourney changes their policies.

## Installation

```bash
uv sync
playwright install chromium
```

`uv sync` installs all dependencies. Then run `playwright install chromium` to set up the browser for login.

After installation, the `midjourney` command is available anywhere.

## First-Time Setup

### 1. Login

A browser window will open. Sign in with your Google account. The refresh token will be saved automatically to `.env`.

```bash
midjourney login
```

After this, the token renews automatically — no repeated login needed.

### Manual Token Setup (Alternative)

You can also set the token directly instead of using browser login.

1. Copy `.env.example` to `.env`
2. Open browser DevTools → Application → Cookies, copy the value of `__Host-Midjourney.AuthUserTokenV3_r`
3. Paste into `.env`

```bash
cp .env.example .env
# Edit .env and paste your token after MJ_REFRESH_TOKEN=
```

## CLI Usage

### Generate Images

```bash
# Basic
midjourney imagine "a red apple on a wooden table"

# With parameters
midjourney imagine "cyberpunk cityscape" --ar 16:9 -s 300 -c 20

# Image references (local files are uploaded automatically)
midjourney imagine "a dog" --image ./photo.png --sref ./style.png --oref ./char.png

# Full options
midjourney imagine "watercolor mountains" \
  --ar 3:2 \
  -s 500 \
  -q 2 \
  --raw \
  --mode fast \
  --visibility stealth \
  -o ./my_images \
  --size 1024
```

### Post-processing

```bash
# Vary (Strong/Subtle)
midjourney vary <job_id> 0              # Strong (default)
midjourney vary <job_id> 0 --subtle     # Subtle

# Upscale (2x)
midjourney upscale <job_id> 0           # Subtle (default)
midjourney upscale <job_id> 0 --type creative

# Pan (extend)
midjourney pan <job_id> 0 -d up
midjourney pan <job_id> 0 -d left -p "new prompt for panned area"
```

> **Upscale is terminal** — you cannot pan/vary from an upscaled result. Always branch from the original grid job.

### Animation (Video Generation)

```bash
# Generate animation from an imagine result (Image-to-Video)
midjourney animate <job_id> 0

# Generate from image files
midjourney animate-from-image ./start.png                       # start only
midjourney animate-from-image ./start.png ./end.png             # start+end
midjourney animate-from-image ./start.png loop --motion high    # start+loop

# Post-process existing video jobs
midjourney loop-video <job_id>                      # create looping version
midjourney extend-video <job_id> --motion low       # extend (motion: low/high)
midjourney extend-video <job_id> --motion high

# Download video
midjourney download-video <job_id>                  # raw (.mp4)
midjourney download-video <job_id> --size 1080      # social resolution
```

### List Recent Jobs

```bash
midjourney list
midjourney list -n 50    # up to 50 jobs
```

### Download Images

```bash
midjourney download <job_id> -o ./images --size 1024
```

## Python Library Usage

### Basic Usage

```python
from midjourney_api import MidjourneyClient

with MidjourneyClient(print_log=True) as client:  # print_log=False by default
    job = client.imagine(
        "a red apple",
        ar="16:9",
        stylize=200,
        chaos=10,
    )
    paths = client.download_images(job, "./images", size=1024)
```

To enable HTTP error debug logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # shows detailed HTTP error output from api.py
```

### Download as Bytes (No Disk I/O)

```python
from io import BytesIO
from PIL import Image

with MidjourneyClient() as client:
    job = client.imagine("landscape", ar="16:9")
    data_list = client.download_images_bytes(job, size=1024)
    images = [Image.open(BytesIO(data)).convert("RGB") for data in data_list]
```

### Animation Python API

```python
with MidjourneyClient(print_log=True) as client:
    # 1. Animate from imagine result (Image-to-Video)
    imagine_job = client.imagine("a black cat in moonlight", ar="1:1")
    video_job = client.animate(imagine_job.id, index=0)
    path = client.download_video(video_job, "./videos")
    print(video_job.video_url())            # raw mp4
    print(video_job.video_url(size=1080))   # social
    print(video_job.gif_url())              # gif

    # 2. Animate from image files (3 modes)
    job_start_only = client.animate_from_image("./start.png")
    job_start_end  = client.animate_from_image("./start.png", "./end.png")
    job_loop       = client.animate_from_image("./start.png", "loop", motion="high")

    # 3. Post-process existing video jobs
    looped   = client.loop_video(video_job.id)
    extended = client.extend_video(video_job.id, motion="low")

    # 4. Get video as bytes (no disk I/O)
    raw_bytes = client.download_video_bytes(video_job)
```

### Image References — Auto-upload via Client

When using `MidjourneyClient`, local files are uploaded automatically.
Local path → client uploads → CDN URL → inserted into prompt.

Three types of image references with their weight parameters:

| Reference | Weight | Purpose |
|-----------|--------|---------|
| `image` (image prompt) | `iw` (0–3.0, default 1) | Strength of input image influence |
| `sref` (style reference) | `sw` (0–1000, default 100) | Strength of style influence |
| `oref` (object reference) | `ow` (1–1000, default 100) | Strength of object influence |

```python
with MidjourneyClient() as client:
    job = client.imagine(
        "a dog in fantasy landscape",
        image="./images/ref.webp",      # auto-uploaded
        iw=1.5,                         # image prompt weight
        sref="./images/style.webp",     # auto-uploaded (code also works: sref="4440286598")
        sw=300,                         # style reference weight
        oref="./images/char.webp",      # auto-uploaded (URL/file only, no codes)
        ow=80,                          # object reference weight
        ar="16:9",
    )
```

### Image References — Direct V7Params

When building `V7Params` directly, you must handle uploads yourself.
Parameter types (`OmniRef`, `StyleRef`, etc.) are prompt values and accept URLs only.

```python
from midjourney_api.api import MidjourneyAPI
from midjourney_api.auth import MidjourneyAuth
from midjourney_api.params.v7 import V7Params
from midjourney_api.params.types import AspectRatio, OmniRef, OmniWeight, StyleRef, StyleWeight

auth = MidjourneyAuth()
api = MidjourneyAPI(auth)

# 1) Upload local files → get CDN URLs
oref_url = api.upload_image("./images/char.webp")
sref_url = api.upload_image("./images/style.webp")

# 2) Build V7Params with typed values
p = V7Params(
    prompt="a dog in fantasy landscape",
    ar=AspectRatio("16:9"),
    sref=StyleRef(sref_url),       # URL or code
    sw=StyleWeight(300),
    oref=OmniRef(oref_url),        # URL only
    ow=OmniWeight(80),
)
p.validate()

# 3) Submit
job = api.submit_job(p)
```

### Post-processing Pipeline

```python
with MidjourneyClient() as client:
    # imagine → vary → upscale / pan
    job = client.imagine("a cat in a magical forest", ar="1:1")

    varied = client.vary(job.id, index=0, strong=True)
    upscaled = client.upscale(varied.id, index=0, upscale_type="v7_2x_subtle")

    # pan must be from a grid job (not from an upscaled result)
    panned = client.pan(varied.id, index=0, direction="up")

    client.download_images(upscaled, "./images/upscaled")
    client.download_images(panned, "./images/panned")
```

### Parameter System

Two ways to create parameters:

```python
# 1) create_params — auto-casts raw values (int, str, bool)
from midjourney_api.params import create_params

p = create_params(
    version=7,
    prompt="a sunset",
    ar="16:9",
    stylize=500,
    speed="fast",           # str → SpeedMode.FAST
    visibility="stealth",   # str → VisibilityMode.STEALTH
)
p.validate()
print(p.build_prompt())
# → a sunset --v 7 --ar 16:9 --s 500 --fast --stealth

# 2) V7Params — pass typed instances directly
from midjourney_api.params.v7 import V7Params
from midjourney_api.params.types import AspectRatio, Stylize, SpeedMode, VisibilityMode

p = V7Params(
    prompt="a sunset",
    ar=AspectRatio("16:9"),
    stylize=Stylize(500),
    speed=SpeedMode.FAST,
    visibility=VisibilityMode.STEALTH,
)
```

## Type System

All parameters are custom types that inherit from Python primitives (`int`, `str`, `float`).
Value ranges are validated at construction time; `to_prompt(version)` generates the prompt fragment.

```python
from midjourney_api.params.types import Stylize, SpeedMode, Version

Stylize(500)        # OK
Stylize(1001)       # ValidationError: stylize must be 0-1000
SpeedMode("fast")   # SpeedMode.FAST
SpeedMode("slow")   # ValidationError: SpeedMode must be one of [...]
```

| Category | Types | Base | Description |
|----------|-------|------|-------------|
| Range int | `Stylize`, `Chaos`, `Weird`, `Stop`, `Seed`, `StyleWeight`, `OmniWeight` | `int` | Range-limited |
| Discrete int | `Quality` | `int` | Only 1, 2, 4 allowed |
| Range float | `ImageWeight` | `float` | Range-limited |
| String | `AspectRatio`, `StyleRef`, `OmniRef`, `Personalize` | `str` | Format-validated |
| Flag | `Tile`, `Raw`, `Draft` | `int` | bool-like (True/False) |
| Mode Enum | `SpeedMode`, `VisibilityMode` | `StrEnum` | Mutually exclusive |
| Version | `Version`, `Niji` | `int` | Only supported versions (`--v 7` / `--niji 7`) |

### SpeedMode / VisibilityMode

Mutually exclusive parameters are implemented as `StrEnum`, making invalid combinations structurally impossible.

```python
from midjourney_api.params.types import SpeedMode, VisibilityMode

SpeedMode.FAST          # --fast
SpeedMode.RELAX         # --relax
SpeedMode.TURBO         # --turbo

VisibilityMode.STEALTH  # --stealth
VisibilityMode.PUBLIC   # --public
```

## V7 Supported Parameters

| Parameter | CLI Flag | Python kwarg | Type | Range |
|-----------|----------|--------------|------|-------|
| Aspect Ratio | `--ar` | `ar` | `AspectRatio` | `w:h` (e.g. `16:9`) |
| Stylize | `-s` | `stylize` | `Stylize` | 0–1000 |
| Chaos | `-c` | `chaos` | `Chaos` | 0–100 |
| Quality | `-q` | `quality` | `Quality` | 1, 2, 4 |
| Weird | `-w` | `weird` | `Weird` | 0–3000 |
| Seed | `--seed` | `seed` | `Seed` | 0–4294967295 |
| Tile | `--tile` | `tile` | `Tile` | flag |
| Raw | `--raw` | `raw` | `Raw` | flag |
| Draft | `--draft` | `draft` | `Draft` | flag |
| No (negative) | `--no` | `no` | `str` | text |
| **References** | | | | |
| Image Prompt | `--image` | `image` | file/URL | image prompt |
| Image Weight | `--iw` | `iw` | `ImageWeight` | 0–3.0 (default 1) |
| Style Ref | `--sref` | `sref` | `StyleRef` | URL/file/code |
| Style Weight | `--sw` | `sw` | `StyleWeight` | 0–1000 (default 100) |
| Omni Ref | `--oref` | `oref` | `OmniRef` | URL/file only (no codes) |
| Omni Weight | `--ow` | `ow` | `OmniWeight` | 1–1000 (default 100) |
| Personalize | `-p` | `personalize` | `Personalize` | code string (e.g. `ebcd5dd7-...`) or empty string (default profile) |
| Niji | `--niji` | `niji` | `Niji` | version int (e.g. 7), replaces `--v` |
| Speed | `--mode` | `speed` | `SpeedMode` | fast/relax/turbo |
| Visibility | `--visibility` | `visibility` | `VisibilityMode` | stealth/public |

## Project Structure

```
├── pyproject.toml              # package config (uv sync)
├── midjourney_api/
│   ├── __init__.py             # public API exports
│   ├── cli.py                  # CLI implementation (argparse)
│   ├── client.py               # MidjourneyClient (high-level API)
│   ├── api.py                  # REST API wrapper (upload, submit, query)
│   ├── auth.py                 # Firebase auth / token management
│   ├── models.py               # Job, UserSettings data models
│   ├── exceptions.py           # exception classes
│   └── params/
│       ├── __init__.py         # create_params() factory (casting)
│       ├── base.py             # BaseParams (ABC)
│       ├── types.py            # custom types (MJParam, _Flag, _RangeInt, StrEnum, etc.)
│       └── v7.py               # V7Params (V7 parameter set)
├── examples/
│   └── basic_usage.py          # usage examples + parameter tests
├── .env.example
└── config.example.json
```

## Dependencies

- Python 3.11+
- `curl_cffi` — HTTP client (Chrome TLS fingerprint for Cloudflare bypass)
- `python-dotenv` — `.env` file loading
- `httpx` — Firebase token refresh
- `playwright` — browser-based login
