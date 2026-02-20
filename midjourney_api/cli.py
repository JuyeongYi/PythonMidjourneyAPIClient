#!/usr/bin/env python3
"""Command-line interface for Midjourney API client."""

from __future__ import annotations

import argparse

from midjourney_api.const import UpscaleType
from midjourney_api.params.types import (
    AspectRatio,
    Chaos,
    ImageWeight,
    OmniWeight,
    Quality,
    Seed,
    SpeedMode,
    Stop,
    StyleWeight,
    Stylize,
    VisibilityMode,
    Weird,
)


def cmd_login(args: argparse.Namespace) -> None:
    """Handle the login command."""
    from midjourney_api.client import MidjourneyClient

    client = MidjourneyClient(env_path=args.env, print_log=args.verbose)
    client.login(force=args.force)
    client.close()


def cmd_imagine(args: argparse.Namespace) -> None:
    """Handle the imagine command."""
    from midjourney_api.client import MidjourneyClient

    params = {}
    if args.ar:
        params["ar"] = args.ar
    if args.stylize is not None:
        params["stylize"] = args.stylize
    if args.chaos is not None:
        params["chaos"] = args.chaos
    if args.quality is not None:
        params["quality"] = args.quality
    if args.seed is not None:
        params["seed"] = args.seed
    if args.weird is not None:
        params["weird"] = args.weird
    if args.stop is not None:
        params["stop"] = args.stop
    if args.no:
        params["no"] = args.no
    if args.iw is not None:
        params["iw"] = args.iw
    if args.tile:
        params["tile"] = True
    if args.raw:
        params["raw"] = True
    if args.draft:
        params["draft"] = True
    if args.sref:
        params["sref"] = args.sref
    if args.oref:
        params["oref"] = args.oref
    if args.ow is not None:
        params["ow"] = args.ow
    if args.sw is not None:
        params["sw"] = args.sw
    if args.niji is not None:
        params["niji"] = args.niji
    if args.personalize is not None:
        params["personalize"] = args.personalize
    if args.visibility:
        params["visibility"] = args.visibility

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.imagine(
            args.prompt,
            image=args.image,
            version=args.version,
            mode=args.mode,
            **params,
        )
        print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_list(args: argparse.Namespace) -> None:
    """Handle the list command."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        jobs = client.list_jobs(limit=args.limit)
        for job in jobs:
            status_icon = {"completed": "+", "failed": "x", "running": "~"}.get(
                job.status, "?"
            )
            print(f"[{status_icon}] {job.id}  {job.prompt[:60]}")


def cmd_vary(args: argparse.Namespace) -> None:
    """Handle the vary command."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.vary(
            args.job_id, args.index,
            strong=(not args.subtle),
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_upscale(args: argparse.Namespace) -> None:
    """Handle the upscale command."""
    from midjourney_api.client import MidjourneyClient

    type_map = {"subtle": UpscaleType.SUBTLE, "creative": UpscaleType.CREATIVE}
    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.upscale(
            args.job_id, args.index,
            upscale_type=type_map[args.type],
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_pan(args: argparse.Namespace) -> None:
    """Handle the pan command."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.pan(
            args.job_id, args.index,
            direction=args.direction,
            prompt=args.prompt or "",
            mode=args.mode,
        )
        print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_animate(args: argparse.Namespace) -> None:
    """Handle the animate command (i2v from imagine)."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.animate(
            args.job_id, args.index,
            prompt=args.prompt,
            motion=args.motion,
            batch_size=args.batch_size,
            resolution=args.resolution,
            mode=args.mode,
            stealth=args.stealth,
        )
        print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_animate_from_image(args: argparse.Namespace) -> None:
    """Handle the animate-from-image command (start / start+end / start+loop)."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.animate_from_image(
            args.start_image,
            args.end_image,
            motion=args.motion,
            prompt=args.prompt,
            batch_size=args.batch_size,
            resolution=args.resolution,
            mode=args.mode,
            stealth=args.stealth,
        )
        print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_extend_video(args: argparse.Namespace) -> None:
    """Handle the extend-video command."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.extend_video(
            args.job_id,
            args.index,
            motion=args.motion,
            loop=args.loop,
            batch_size=args.batch_size,
            resolution=args.resolution,
            mode=args.mode,
            stealth=args.stealth,
        )
        print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_download_video(args: argparse.Namespace) -> None:
    """Handle the download-video command."""
    from midjourney_api.client import MidjourneyClient
    from midjourney_api.models import Job

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = Job(id=args.job_id, prompt="", status="completed",
                  user_id=client.user_id, event_type="video_diffusion")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_download(args: argparse.Namespace) -> None:
    """Handle the download command."""
    from midjourney_api.client import MidjourneyClient
    from midjourney_api.models import Job

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = Job(id=args.job_id, prompt="", status="completed", user_id=client.user_id)
        client.download_images(job, args.output, size=args.size)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Midjourney API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress logs")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    p_login = sub.add_parser("login", help="Login via browser (Playwright)")
    p_login.add_argument(
        "--force", "-f",
        action="store_true",
        help="Clear cached browser session before login (use to switch accounts)",
    )

    # imagine
    p_imagine = sub.add_parser("imagine", help="Generate images from a prompt")
    p_imagine.add_argument("prompt", help="Text prompt")
    p_imagine.add_argument("--image", help="Image prompt (local file or URL)")
    p_imagine.add_argument("--iw", type=ImageWeight, help="Image weight 0-3 (default 1)")
    p_imagine.add_argument("--ar", type=AspectRatio, help="Aspect ratio (e.g., 16:9)")
    p_imagine.add_argument("-s", "--stylize", type=Stylize, help="0-1000")
    p_imagine.add_argument("-c", "--chaos", type=Chaos, help="0-100")
    p_imagine.add_argument("-q", "--quality", type=Quality, help="1, 2, or 4")
    p_imagine.add_argument("--seed", type=Seed, help="0-4294967295")
    p_imagine.add_argument("-w", "--weird", type=Weird, help="0-3000")
    p_imagine.add_argument("--stop", type=Stop, help="10-100")
    p_imagine.add_argument("--no", help="Negative prompt (comma separated)")
    p_imagine.add_argument("--tile", action="store_true", help="Enable tile mode")
    p_imagine.add_argument("--raw", action="store_true", help="Enable raw mode")
    p_imagine.add_argument("--draft", action="store_true", help="Enable draft mode")
    p_imagine.add_argument("--sref", help="Style reference (local file, URL, or code)")
    p_imagine.add_argument("--oref", help="Object/character reference (local file or URL)")
    p_imagine.add_argument("--ow", type=OmniWeight, help="1-1000, default 100")
    p_imagine.add_argument("--sw", type=StyleWeight, help="0-1000, default 100")
    p_imagine.add_argument("-p", "--personalize", nargs="?", const="", default=None,
                           help="Personalization code (omit value for default)")
    p_imagine.add_argument("--niji", type=int, default=None, help="Niji model version (e.g. 7)")
    p_imagine.add_argument("-v", "--version", type=int, default=7, help="Model version")
    p_imagine.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_imagine.add_argument("--visibility", type=VisibilityMode, default=None)
    p_imagine.add_argument("-o", "--output", default="./images", help="Output directory")
    p_imagine.add_argument("--size", type=int, default=640, help="Image download size")

    # vary
    p_vary = sub.add_parser("vary", help="Create a variation of an image")
    p_vary.add_argument("job_id", help="Parent job ID")
    p_vary.add_argument("index", type=int, help="Image index (0-3)")
    p_vary.add_argument("--subtle", action="store_true", help="Subtle variation (default: Strong)")
    p_vary.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_vary.add_argument("-o", "--output", default="./images", help="Output directory")
    p_vary.add_argument("--size", type=int, default=640, help="Image download size")

    # upscale
    p_upscale = sub.add_parser("upscale", help="Upscale an image")
    p_upscale.add_argument("job_id", help="Parent job ID")
    p_upscale.add_argument("index", type=int, help="Image index (0-3)")
    p_upscale.add_argument("--type", default="subtle", choices=["subtle", "creative"],
                           help="Upscale type (default: subtle)")
    p_upscale.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_upscale.add_argument("-o", "--output", default="./images", help="Output directory")
    p_upscale.add_argument("--size", type=int, default=640, help="Image download size")

    # pan
    p_pan = sub.add_parser("pan", help="Pan (extend) an image in a direction")
    p_pan.add_argument("job_id", help="Parent job ID")
    p_pan.add_argument("index", type=int, help="Image index (0-3)")
    p_pan.add_argument("-d", "--direction", default="up",
                       choices=["up", "down", "left", "right"], help="Pan direction")
    p_pan.add_argument("-p", "--prompt", default="", help="Prompt for panned area")
    p_pan.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_pan.add_argument("-o", "--output", default="./images", help="Output directory")
    p_pan.add_argument("--size", type=int, default=640, help="Image download size")

    # animate (i2v from imagine)
    p_animate = sub.add_parser("animate", help="Generate animation from an imagine job")
    p_animate.add_argument("job_id", help="Source imagine job ID")
    p_animate.add_argument("index", type=int, help="Image index (0-3)")
    p_animate.add_argument("-p", "--prompt", default="", help="Additional prompt text")
    p_animate.add_argument("--motion", choices=["low", "high"], default=None,
                           help="Motion intensity (low or high)")
    p_animate.add_argument("--batch-size", type=int, default=1, dest="batch_size",
                           help="Number of video variants to generate (default: 1)")
    p_animate.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
    p_animate.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_animate.add_argument("--stealth", action="store_true", help="Generate in stealth mode")
    p_animate.add_argument("-o", "--output", default="./videos", help="Output directory")
    p_animate.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

    # animate-from-image (start / start+end / start+loop)
    p_afi = sub.add_parser("animate-from-image", help="Generate animation from image files")
    p_afi.add_argument("start_image", help="Start frame (local file or URL)")
    p_afi.add_argument("end_image", nargs="?", default=None,
                       help="End frame (local file or URL), 'loop' for looping, or omit for start-only")
    p_afi.add_argument("--motion", choices=["low", "high"], default=None,
                       help="Motion intensity (required for loop mode)")
    p_afi.add_argument("-p", "--prompt", default="", help="Text prompt")
    p_afi.add_argument("--batch-size", type=int, default=1, dest="batch_size",
                       help="Number of video variants to generate (default: 1)")
    p_afi.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
    p_afi.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_afi.add_argument("--stealth", action="store_true", help="Generate in stealth mode")
    p_afi.add_argument("-o", "--output", default="./videos", help="Output directory")
    p_afi.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

    # extend-video
    p_ext = sub.add_parser("extend-video", help="Extend an existing video job (or make it loop)")
    p_ext.add_argument("job_id", help="Source video job ID")
    p_ext.add_argument("index", type=int, nargs="?", default=0, help="Batch variant index (default: 0)")
    p_ext.add_argument("--loop", action="store_true",
                       help="Create a seamless loop instead of extending")
    p_ext.add_argument("--motion", choices=["low", "high"], default=None,
                       help="Motion intensity (low or high, non-loop only)")
    p_ext.add_argument("--batch-size", type=int, default=1, dest="batch_size",
                       help="Number of video variants to generate (default: 1)")
    p_ext.add_argument("--resolution", default="480", help="Video resolution (default: 480)")
    p_ext.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_ext.add_argument("--stealth", action="store_true", help="Generate in stealth mode")
    p_ext.add_argument("-o", "--output", default="./videos", help="Output directory")
    p_ext.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

    # download-video
    p_dlv = sub.add_parser("download-video", help="Download video for a completed video job")
    p_dlv.add_argument("job_id", help="Video job ID")
    p_dlv.add_argument("--batch-size", type=int, default=1, dest="batch_size",
                       help="Number of variants to download (default: 1)")
    p_dlv.add_argument("-o", "--output", default="./videos", help="Output directory")
    p_dlv.add_argument("--size", type=int, default=None, help="Social resolution (e.g. 1080)")

    # list
    p_list = sub.add_parser("list", help="List recent jobs")
    p_list.add_argument("-n", "--limit", type=int, default=20, help="Max jobs to list")

    # download
    p_dl = sub.add_parser("download", help="Download images for a job")
    p_dl.add_argument("job_id", help="Job ID to download")
    p_dl.add_argument("-o", "--output", default="./images", help="Output directory")
    p_dl.add_argument("--size", type=int, default=640, help="Image download size")

    args = parser.parse_args()

    handlers = {
        "login": cmd_login,
        "imagine": cmd_imagine,
        "vary": cmd_vary,
        "upscale": cmd_upscale,
        "pan": cmd_pan,
        "animate": cmd_animate,
        "animate-from-image": cmd_animate_from_image,
        "extend-video": cmd_extend_video,
        "download-video": cmd_download_video,
        "list": cmd_list,
        "download": cmd_download,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
