"""Basic usage examples for the Midjourney API client."""

from midjourney import MidjourneyClient
from midjourney.params import create_params


# --- Example 1: Simple image generation ---
def simple_generation():
    with MidjourneyClient() as client:
        job = client.imagine("a red apple on a wooden table")
        print(f"Job ID: {job.id}")
        print(f"Status: {job.status}")
        if job.is_completed:
            paths = client.download_images(job, "./images")
            print(f"Downloaded {len(paths)} images")


# --- Example 2: With parameters ---
def parameterized_generation():
    with MidjourneyClient() as client:
        job = client.imagine(
            "cyberpunk cityscape at sunset",
            ar="16:9",
            stylize=300,
            chaos=20,
            quality=2,
        )
        if job.is_completed:
            client.download_images(job, "./images", size=1024)


# --- Example 3: Using the parameter system directly ---
def direct_params():
    params = create_params(
        version=7,
        prompt="watercolor painting of mountains",
        ar="3:2",
        stylize=500,
        raw=True,
    )
    params.validate()
    print(f"Full prompt: {params.build_prompt()}")
    # Output: watercolor painting of mountains --v 7 --ar 3:2 --s 500 --raw


# --- Example 4: Full postprocess pipeline ---
# imagine → vary → upscale / pan (upscale 후 pan 불가)
def postprocess_pipeline():
    with MidjourneyClient() as client:
        # 1) Generate
        job = client.imagine("a cat in a magical forest", ar="1:1")
        print(f"Imagine: {job.id} ({len(job.image_urls)} images)")

        # 2) Vary — first image, Strong variation
        varied = client.vary(job.id, index=0, strong=True)
        print(f"Vary:    {varied.id} ({len(varied.image_urls)} images)")

        # 3) Upscale — first image of the varied result
        upscaled = client.upscale(varied.id, index=0, upscale_type="v7_2x_subtle")
        print(f"Upscale: {upscaled.id} ({len(upscaled.image_urls)} images)")

        # 4) Pan — from varied result (NOT upscaled; upscale is a terminal operation)
        panned = client.pan(
            varied.id, index=0,
            direction="up",
            prompt="a cat in a magical forest --ar 1:1",
        )
        print(f"Pan:     {panned.id} ({len(panned.image_urls)} images)")

        # Download final results
        client.download_images(upscaled, "./images/upscaled", size=1024)
        client.download_images(panned, "./images/panned", size=1024)


# --- Example 5: List recent jobs ---
def list_recent():
    with MidjourneyClient() as client:
        jobs = client.list_jobs(limit=5)
        for job in jobs:
            print(f"{job.id}: {job.status} - {job.prompt[:50]}")


# --- Example 6: Image references ---
# MidjourneyClient를 사용하면 로컬 파일을 자동 업로드한다.
# 로컬 경로 → client가 업로드 → CDN URL → OmniRef/StyleRef → 프롬프트
def image_references_via_client():
    with MidjourneyClient() as client:
        job = client.imagine(
            "a dog in fantasy landscape",
            image="./images/ref.webp",      # 자동 업로드
            sref="./images/style.webp",      # 자동 업로드
            sw=300,
            oref="./images/char.webp",       # 자동 업로드
            ow=80,
            ar="16:9",
        )


# V7Params를 직접 만들 때는 업로드를 직접 처리해야 한다.
# OmniRef/StyleRef 등은 프롬프트 파라미터이므로 URL만 허용한다.
def image_references_via_params():
    from midjourney.api import MidjourneyAPI
    from midjourney.auth import MidjourneyAuth
    from midjourney.params.v7 import V7Params
    from midjourney.params.types import (
        AspectRatio, OmniRef, OmniWeight, StyleRef, StyleWeight,
    )

    auth = MidjourneyAuth()
    api = MidjourneyAPI(auth)
    try:
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
        print(f"Job ID: {job.id}")
    finally:
        api.close()


# --- Example 7: Download by job ID ---
def download_existing():
    from midjourney.models import Job

    with MidjourneyClient() as client:
        job = Job(id="your-job-id-here", prompt="", status="completed")
        client.download_images(job, "./images")


# --- Example 8: All parameters test (no auth required) ---
def all_params_test():
    from midjourney.params.types import (
        AspectRatio, Chaos, Draft, ImageWeight, Niji,
        OmniRef, OmniWeight, Personalize, Quality,
        Raw, Seed, SpeedMode, Stop, StyleRef,
        StyleWeight, Stylize, Tile, Version, VisibilityMode, Weird,
    )


    # -- Validation errors --
    from midjourney.exceptions import ValidationError
    import traceback

    error_cases = [
        ("Stylize(-1)", lambda: Stylize(-1)),
        ("Stylize(1001)", lambda: Stylize(1001)),
        ("Chaos(101)", lambda: Chaos(101)),
        ("Weird(3001)", lambda: Weird(3001)),
        ("Stop(9)", lambda: Stop(9)),
        ("Stop(101)", lambda: Stop(101)),
        ("Seed(-1)", lambda: Seed(-1)),
        ("Quality(3)", lambda: Quality(3)),
        ("ImageWeight(4)", lambda: ImageWeight(4)),
        ("StyleWeight(-1)", lambda: StyleWeight(-1)),
        ("OmniWeight(0)", lambda: OmniWeight(0)),
        ("OmniWeight(1001)", lambda: OmniWeight(1001)),
        ("AspectRatio('bad')", lambda: AspectRatio("bad")),
        ("OmniRef('code123')", lambda: OmniRef("code123")),
        ("Version(6)", lambda: Version(6)),
        ("SpeedMode('slow')", lambda: SpeedMode("slow")),
        ("VisibilityMode('hidden')", lambda: VisibilityMode("hidden")),
        ("Niji(0)", lambda: Niji(0)),
    ]
    for label, fn in error_cases:
        try:
            fn()
            assert False, f"{label} should have raised ValidationError"
        except ValidationError:
            pass

    # -- Full prompt build (using typed instances directly) --
    from midjourney.params.v7 import V7Params

    p = V7Params(
        prompt="a red apple",
        ar=AspectRatio("16:9"),
        stylize=Stylize(500),
        chaos=Chaos(50),
        quality=Quality(2),
        seed=Seed(42),
        weird=Weird(100),
        iw=ImageWeight(1.5),
        tile=Tile(True),
        raw=Raw(True),
        sref=StyleRef("4440286598"),
        sw=StyleWeight(200),
        oref=OmniRef("https://upload.wikimedia.org/wikipedia/en/7/7d/Lenna_%28test_image%29.png"),
        ow=OmniWeight(50),
        speed=SpeedMode.TURBO,
        visibility=VisibilityMode.STEALTH,
    )
    p.validate()
    result = p.build_prompt()
    print(f"Full prompt: {result}")

    # -- Cross-field validation --
    try:
        p_bad = V7Params(prompt="test", sw=StyleWeight(100))
        p_bad.validate()
        assert False, "sw without sref should fail"
    except ValidationError:
        pass

    try:
        p_bad = V7Params(prompt="test", ow=OmniWeight(100))
        p_bad.validate()
        assert False, "ow without oref should fail"
    except ValidationError:
        pass

    try:
        p_bad = V7Params(
            prompt="test", niji=Niji(7),
            oref=OmniRef("https://example.com/img.png"),
        )
        p_bad.validate()
        assert False, "niji + oref should fail"
    except ValidationError:
        pass

    # -- Niji prompt --
    p_niji = V7Params(prompt="anime cat", niji=Niji(7), ar=AspectRatio("16:9"))
    p_niji.validate()
    assert "--niji 7" in p_niji.build_prompt()
    assert "--v 7" not in p_niji.build_prompt()

    # -- create_params casting (raw → typed) --
    p2 = create_params(version=7, prompt="test", speed="fast", visibility="public")
    p2.validate()
    assert "--fast" in p2.build_prompt()
    assert "--public" in p2.build_prompt()

    print("All parameter tests passed!")


if __name__ == "__main__":
    # -- Actual API submission using V7Params directly --
    from midjourney.api import MidjourneyAPI
    from midjourney.auth import MidjourneyAuth
    from midjourney.params.v7 import V7Params
    from midjourney.params.types import (
        AspectRatio, Chaos, ImageWeight, OmniRef, OmniWeight,
        Personalize, Quality, Raw, Seed, SpeedMode, StyleRef,
        StyleWeight, Stylize, Tile, VisibilityMode, Weird, Niji
    )

    p = V7Params(
        prompt="a red apple on a wooden table",
        ar=AspectRatio("16:9"),
        stylize=Stylize(500),
        chaos=Chaos(50),
        seed=Seed(42),
        weird=Weird(100),
        iw=ImageWeight(1.5),
        raw=Raw(True),
        sref=StyleRef("4440286598"),
        sw=StyleWeight(200),
        speed=SpeedMode.FAST,
        visibility=VisibilityMode.STEALTH,
        niji=Niji(7),
    )
    p.validate()
    print(f"Submitting: {p.build_prompt()}")

    auth = MidjourneyAuth()
    api = MidjourneyAPI(auth)
    try:
        # oref용 이미지 업로드 → CDN URL 획득
        oref_cdn = api.upload_image("./images/char.webp")
        print(f"Uploaded oref: {oref_cdn}")

        job = api.submit_job(p)
        print(f"Job ID: {job.id}")
    finally:
        api.close()
