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


# --- Example 6: Download by job ID ---
def download_existing():
    from midjourney.models import Job

    with MidjourneyClient() as client:
        job = Job(id="your-job-id-here", prompt="", status="completed")
        client.download_images(job, "./images")


if __name__ == "__main__":
    # Run the parameter demo (doesn't require authentication)
    postprocess_pipeline()
