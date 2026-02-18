# Midjourney Python API Client

Midjourney 웹사이트의 비공식 Python API 클라이언트. 프로그래밍 방식으로 이미지를 생성하고 다운로드할 수 있다.

> **주의**: 비공식 API를 사용하므로 Midjourney 정책 변경 시 동작하지 않을 수 있음.

## 설치

```bash
uv sync
```

`uv sync`만으로 Playwright(브라우저 로그인)를 포함한 전체 의존성이 설치된다.

배포용으로 Playwright 없이 설치하려면:

```bash
uv sync --no-group dev
```

설치 후 `midjourney` 명령어를 어디서든 사용할 수 있다.

## 처음 실행 시 해야 하는 일

### 1. 로그인

브라우저가 열리면 Google 계정으로 로그인한다. 완료되면 Refresh 토큰이 `.env`에 자동 저장된다.

```bash
midjourney login
```

이후 별도의 로그인 없이 토큰이 자동 갱신된다.

### 수동 토큰 설정 (대안)

브라우저 로그인 대신 직접 토큰을 설정할 수도 있다.

1. `.env.example`을 `.env`로 복사
2. 브라우저 개발자 도구 → Application → Cookies에서 `__Host-Midjourney.AuthUserTokenV3_r` 값을 복사
3. `.env`에 붙여넣기

```bash
cp .env.example .env
# .env 파일을 열어 MJ_REFRESH_TOKEN= 뒤에 토큰 붙여넣기
```

## CLI 사용법

### 이미지 생성

```bash
# 기본
midjourney imagine "a red apple on a wooden table"

# 파라미터 지정
midjourney imagine "cyberpunk cityscape" --ar 16:9 -s 300 -c 20

# 이미지 참조 (로컬 파일 자동 업로드)
midjourney imagine "a dog" --image ./photo.png --sref ./style.png --oref ./char.png

# 전체 옵션
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

### 후처리 (Postprocess)

```bash
# Vary (Strong/Subtle)
midjourney vary <job_id> 0              # Strong (기본)
midjourney vary <job_id> 0 --subtle     # Subtle

# Upscale (2x)
midjourney upscale <job_id> 0           # Subtle (기본)
midjourney upscale <job_id> 0 --type creative

# Pan (확장)
midjourney pan <job_id> 0 -d up
midjourney pan <job_id> 0 -d left -p "new prompt for panned area"
```

> **Upscale은 터미널 작업** — upscale 결과에서 pan/vary 불가. 반드시 grid job에서 분기해야 한다.

### 최근 작업 목록

```bash
midjourney list
midjourney list -n 50    # 최대 50개
```

### 이미지 다운로드

```bash
midjourney download <job_id> -o ./images --size 1024
```

## Python 라이브러리로 사용

### 기본 사용

```python
from midjourney import MidjourneyClient

with MidjourneyClient() as client:
    job = client.imagine(
        "a red apple",
        ar="16:9",
        stylize=200,
        chaos=10,
    )
    paths = client.download_images(job, "./images", size=1024)
```

### 이미지 참조 — client를 통한 자동 업로드

`MidjourneyClient`를 사용하면 로컬 파일을 자동 업로드한다.
로컬 경로 → client가 업로드 → CDN URL → 프롬프트에 삽입.

세 종류의 이미지 참조와 각각의 가중치 파라미터:

| 참조 | 가중치 | 용도 |
|------|--------|------|
| `image` (이미지 프롬프트) | `iw` (0–3.0, 기본 1) | 입력 이미지 반영 강도 |
| `sref` (스타일 참조) | `sw` (0–1000, 기본 100) | 스타일 반영 강도 |
| `oref` (오브젝트 참조) | `ow` (1–1000, 기본 100) | 오브젝트 반영 강도 |

```python
with MidjourneyClient() as client:
    job = client.imagine(
        "a dog in fantasy landscape",
        image="./images/ref.webp",      # 자동 업로드
        iw=1.5,                         # 이미지 프롬프트 가중치
        sref="./images/style.webp",     # 자동 업로드 (코드도 가능: sref="4440286598")
        sw=300,                         # 스타일 참조 가중치
        oref="./images/char.webp",      # 자동 업로드 (URL만 허용, 코드 불가)
        ow=80,                          # 오브젝트 참조 가중치
        ar="16:9",
    )
```

### 이미지 참조 — V7Params 직접 생성

`V7Params`를 직접 만들 때는 업로드를 직접 처리해야 한다.
파라미터 타입(`OmniRef`, `StyleRef` 등)은 프롬프트 값이므로 URL만 허용한다.

```python
from midjourney.api import MidjourneyAPI
from midjourney.auth import MidjourneyAuth
from midjourney.params.v7 import V7Params
from midjourney.params.types import AspectRatio, OmniRef, OmniWeight, StyleRef, StyleWeight

auth = MidjourneyAuth()
api = MidjourneyAPI(auth)

# 1) 로컬 파일 업로드 → CDN URL 획득
oref_url = api.upload_image("./images/char.webp")
sref_url = api.upload_image("./images/style.webp")

# 2) CDN URL로 타입 생성 → V7Params 조립
p = V7Params(
    prompt="a dog in fantasy landscape",
    ar=AspectRatio("16:9"),
    sref=StyleRef(sref_url),       # URL 또는 코드
    sw=StyleWeight(300),
    oref=OmniRef(oref_url),        # URL만 허용
    ow=OmniWeight(80),
)
p.validate()

# 3) 서밋
job = api.submit_job(p)
```

### 후처리 파이프라인

```python
with MidjourneyClient() as client:
    # imagine → vary → upscale / pan
    job = client.imagine("a cat in a magical forest", ar="1:1")

    varied = client.vary(job.id, index=0, strong=True)
    upscaled = client.upscale(varied.id, index=0, upscale_type="v7_2x_subtle")

    # pan은 grid job에서만 가능 (upscale 결과에서 불가)
    panned = client.pan(varied.id, index=0, direction="up")

    client.download_images(upscaled, "./images/upscaled")
    client.download_images(panned, "./images/panned")
```

### 파라미터 시스템

두 가지 방식으로 파라미터를 생성할 수 있다:

```python
# 1) create_params — 원시값(int, str, bool)을 자동 캐스팅
from midjourney.params import create_params

p = create_params(
    version=7,
    prompt="a sunset",
    ar="16:9",
    stylize=500,
    speed="fast",           # 문자열 → SpeedMode.FAST
    visibility="stealth",   # 문자열 → VisibilityMode.STEALTH
)
p.validate()
print(p.build_prompt())
# → a sunset --v 7 --ar 16:9 --s 500 --fast --stealth

# 2) V7Params — 타입 인스턴스 직접 전달
from midjourney.params.v7 import V7Params
from midjourney.params.types import AspectRatio, Stylize, SpeedMode, VisibilityMode

p = V7Params(
    prompt="a sunset",
    ar=AspectRatio("16:9"),
    stylize=Stylize(500),
    speed=SpeedMode.FAST,
    visibility=VisibilityMode.STEALTH,
)
```

## 타입 시스템

모든 파라미터는 기본 자료형(`int`, `str`, `float`)을 상속한 커스텀 타입이다.
생성 시점에서 값 범위를 검증하고, `to_prompt(version)` 메서드로 프롬프트 조각을 생성한다.

```python
from midjourney.params.types import Stylize, SpeedMode, Version

Stylize(500)        # OK
Stylize(1001)       # ValidationError: stylize must be 0-1000
SpeedMode("fast")   # SpeedMode.FAST
SpeedMode("slow")   # ValidationError: SpeedMode must be one of [...]
```

| 분류 | 타입 | 기반 | 설명 |
|------|------|------|------|
| 범위 정수 | `Stylize`, `Chaos`, `Weird`, `Stop`, `Seed`, `StyleWeight`, `OmniWeight` | `int` | 범위 제한 |
| 이산 정수 | `Quality` | `int` | 1, 2, 4만 허용 |
| 범위 실수 | `ImageWeight` | `float` | 범위 제한 |
| 문자열 | `AspectRatio`, `StyleRef`, `OmniRef`, `Personalize` | `str` | 형식 검증 |
| 플래그 | `Tile`, `Raw`, `Draft`, `Niji` | `int` | bool-like (True/False) |
| 모드 Enum | `SpeedMode`, `VisibilityMode` | `StrEnum` | 상호 배제 |
| 버전 | `Version` | `int` | 지원 버전만 허용 |

### SpeedMode / VisibilityMode

상호 배제 파라미터는 `StrEnum`으로 구현되어, 잘못된 조합이 구조적으로 불가능하다.

```python
from midjourney.params.types import SpeedMode, VisibilityMode

SpeedMode.FAST          # --fast
SpeedMode.RELAX         # --relax
SpeedMode.TURBO         # --turbo

VisibilityMode.STEALTH  # --stealth
VisibilityMode.PUBLIC   # --public
```

## V7 지원 파라미터

| 파라미터 | CLI 플래그 | Python kwarg | 타입 | 값 범위 |
|---------|-----------|--------------|------|---------|
| Aspect Ratio | `--ar` | `ar` | `AspectRatio` | `w:h` (예: `16:9`) |
| Stylize | `-s` | `stylize` | `Stylize` | 0–1000 |
| Chaos | `-c` | `chaos` | `Chaos` | 0–100 |
| Quality | `-q` | `quality` | `Quality` | 1, 2, 4 |
| Weird | `-w` | `weird` | `Weird` | 0–3000 |
| Seed | `--seed` | `seed` | `Seed` | 0–4294967295 |
| Tile | `--tile` | `tile` | `Tile` | flag |
| Raw | `--raw` | `raw` | `Raw` | flag |
| Draft | `--draft` | `draft` | `Draft` | flag |
| No (네거티브) | `--no` | `no` | `str` | 텍스트 |
| **참조** | | | | |
| Image Prompt | `--image` | `image` | 파일/URL | 이미지 프롬프트 |
| Image Weight | `--iw` | `iw` | `ImageWeight` | 0–3.0 (기본 1) |
| Style Ref | `--sref` | `sref` | `StyleRef` | URL/파일/코드 |
| Style Weight | `--sw` | `sw` | `StyleWeight` | 0–1000 (기본 100) |
| Omni Ref | `--oref` | `oref` | `OmniRef` | URL/파일만 (코드 불가) |
| Omni Weight | `--ow` | `ow` | `OmniWeight` | 1–1000 (기본 100) |
| Personalize | — | `personalize` | `Personalize` | 코드/flag |
| Niji | `--niji` | `niji` | `Niji` | flag |
| Speed | `--mode` | `speed` | `SpeedMode` | fast/relax/turbo |
| Visibility | `--visibility` | `visibility` | `VisibilityMode` | stealth/public |

## 프로젝트 구조

```
├── pyproject.toml              # 패키지 설정 (uv sync)
├── midjourney/
│   ├── __init__.py             # 공개 API export
│   ├── cli.py                  # CLI 구현 (argparse)
│   ├── client.py               # MidjourneyClient (고수준 API)
│   ├── api.py                  # REST API 래퍼 (upload, submit, query)
│   ├── auth.py                 # Firebase 인증 / 토큰 관리
│   ├── models.py               # Job, UserSettings 데이터 모델
│   ├── exceptions.py           # 예외 클래스
│   └── params/
│       ├── __init__.py         # create_params() 팩토리 (캐스팅)
│       ├── base.py             # BaseParams (ABC)
│       ├── types.py            # 커스텀 타입 (MJParam, _Flag, _RangeInt, StrEnum 등)
│       └── v7.py               # V7Params (V7 전용 파라미터 셋)
├── examples/
│   └── basic_usage.py          # 사용 예제 + 파라미터 테스트
├── .env.example
└── config.example.json
```

## 의존성

- Python 3.11+
- `curl_cffi` — HTTP 클라이언트 (Chrome TLS 핑거프린트로 Cloudflare 우회)
- `python-dotenv` — `.env` 파일 로드
- `playwright` — 브라우저 기반 로그인 (dev 그룹, `uv sync` 시 자동 포함)
