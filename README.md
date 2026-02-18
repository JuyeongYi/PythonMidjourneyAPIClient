# Midjourney Python API Client

Midjourney 웹사이트의 비공식 Python API 클라이언트. 프로그래밍 방식으로 이미지를 생성하고 다운로드할 수 있다.

> **주의**: 비공식 API를 사용하므로 Midjourney 정책 변경 시 동작하지 않을 수 있음.

## 설치

```bash
pip install -e .
```

Playwright 브라우저 로그인도 사용하려면:

```bash
pip install -e ".[login]"
playwright install chromium
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

# 전체 옵션
midjourney imagine "watercolor mountains" \
  --ar 3:2 \
  -s 500 \
  -q 2 \
  --raw \
  --mode fast \
  -o ./my_images \
  --size 1024
```

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

```python
from midjourney import MidjourneyClient

with MidjourneyClient() as client:
    # 이미지 생성 (완료까지 대기)
    job = client.imagine(
        "a red apple",
        ar="16:9",
        stylize=200,
        chaos=10,
    )

    # 다운로드
    paths = client.download_images(job, "./images", size=1024)
    print(f"저장됨: {paths}")
```

### 대기 없이 제출만

```python
job = client.imagine("prompt here", wait=False)
print(f"제출됨: {job.id}")
```

### 파라미터 시스템 직접 사용

```python
from midjourney.params import create_params

params = create_params(
    version=7,
    prompt="a sunset over the ocean",
    ar="16:9",
    stylize=500,
    raw=True,
)
params.validate()
print(params.build_prompt())
# → a sunset over the ocean --v 7 --ar 16:9 --s 500 --raw
```

## V7 지원 파라미터

| 파라미터 | CLI 플래그 | Python kwarg | 값 범위 | 기본값 |
|---------|-----------|--------------|---------|-------|
| Aspect Ratio | `--ar` | `ar` | `w:h` (예: `16:9`) | `1:1` |
| Stylize | `-s` | `stylize` | 0–1000 | 100 |
| Chaos | `-c` | `chaos` | 0–100 | 0 |
| Quality | `-q` | `quality` | 1, 2, 4 | 1 |
| Weird | `-w` | `weird` | 0–3000 | 0 |
| Seed | `--seed` | `seed` | 0–4294967295 | random |
| Stop | `--stop` | `stop` | 10–100 | 100 |
| Image Weight | — | `iw` | 0–3 | 0.25 |
| Tile | `--tile` | `tile` | flag | off |
| Raw | `--raw` | `raw` | flag | off |
| Draft | `--draft` | `draft` | flag | off |
| No (네거티브) | `--no` | `no` | 텍스트 | — |
| Style Ref | `--sref` | `sref` | URL/코드 | — |
| Style Weight | — | `sw` | 0–1000 | 100 |
| Omni Ref | — | `oref` | URL | — |
| Personalize | — | `personalize` | 코드/flag | — |
| Niji | `--niji` | `niji` | flag | off |
| Mode | `--mode` | `mode` | fast/relax/turbo | fast |

## 프로젝트 구조

```
├── cli.py                     # CLI 진입점 (래퍼)
├── pyproject.toml             # pip install 설정
├── midjourney/
│   ├── __init__.py            # 공개 API export
│   ├── cli.py                 # CLI 구현
│   ├── client.py              # MidjourneyClient (고수준 API)
│   ├── auth.py                # Firebase 인증 / 토큰 관리
│   ├── api.py                 # REST API 래퍼
│   ├── models.py              # Job, UserSettings 데이터 모델
│   ├── exceptions.py          # 예외 클래스
│   └── params/
│       ├── __init__.py        # create_params() 팩토리
│       ├── base.py            # BaseParams (ABC)
│       └── v7.py              # V7Params
├── examples/
│   └── basic_usage.py
├── requirements.txt
├── .env.example
└── config.example.json
```

## 의존성

- Python 3.10+
- `httpx` — HTTP 클라이언트
- `python-dotenv` — `.env` 파일 로드
- `playwright` — 브라우저 기반 로그인 (선택)
