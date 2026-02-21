#!/usr/bin/env python3
"""Midjourney API 클라이언트의 커맨드라인 인터페이스."""

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
    StyleVersion,
    StyleWeight,
    Stylize,
    VisibilityMode,
    Weird,
)


def cmd_login(args: argparse.Namespace) -> None:
    """login 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    client = MidjourneyClient(env_path=args.env, print_log=args.verbose)
    client.login(force=args.force)
    client.close()


def _build_imagine_params(args: argparse.Namespace) -> dict:
    """파싱된 인자에서 선택적 imagine 파라미터를 수집합니다."""
    pairs = [
        ("ar",          args.ar),
        ("stylize",     args.stylize),
        ("chaos",       args.chaos),
        ("quality",     args.quality),
        ("seed",        args.seed),
        ("weird",       args.weird),
        ("stop",        args.stop),
        ("no",          args.no),
        ("iw",          args.iw),
        ("tile",        True if args.tile else None),
        ("raw",         True if args.raw else None),
        ("draft",       True if args.draft else None),
        ("sref",        args.sref),
        ("sw",          args.sw),
        ("sv",          args.sv),
        ("oref",        args.oref),
        ("ow",          args.ow),
        ("niji",        args.niji),
        ("personalize", args.personalize),
        ("visibility",  args.visibility),
    ]
    return {k: v for k, v in pairs if v is not None}


def cmd_imagine(args: argparse.Namespace) -> None:
    """imagine 커맨드를 처리합니다."""
    import sys
    from midjourney_api.client import MidjourneyClient

    if args.version == 8:
        print("Error: Version 8 is not yet implemented.", file=sys.stderr)
        sys.exit(1)

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.imagine(
            args.prompt,
            image=args.image,
            version=args.version,
            mode=args.mode,
            **_build_imagine_params(args),
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_list(args: argparse.Namespace) -> None:
    """list 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        jobs = client.list_jobs(limit=args.limit)
        for job in jobs:
            status_icon = {"completed": "+", "failed": "x", "running": "~"}.get(
                job.status, "?"
            )
            print(f"[{status_icon}] {job.id}  {job.prompt[:60]}")


def cmd_vary(args: argparse.Namespace) -> None:
    """vary 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.vary(
            args.job_id, args.index,
            strong=(not args.subtle),
            mode=args.mode,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_upscale(args: argparse.Namespace) -> None:
    """upscale 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    type_map = {"subtle": UpscaleType.SUBTLE, "creative": UpscaleType.CREATIVE}
    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.upscale(
            args.job_id, args.index,
            upscale_type=type_map[args.type],
            mode=args.mode,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_pan(args: argparse.Namespace) -> None:
    """pan 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.pan(
            args.job_id, args.index,
            direction=args.direction,
            prompt=args.prompt or "",
            mode=args.mode,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_remix(args: argparse.Namespace) -> None:
    """remix 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.remix(
            args.job_id, args.index, args.prompt,
            strong=(not args.subtle),
            mode=args.mode,
            stealth=args.stealth,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_animate(args: argparse.Namespace) -> None:
    """animate 커맨드를 처리합니다 (imagine에서 i2v)."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.animate(
            args.job_id, args.index,
            prompt=args.prompt,
            end_image=args.end_image,
            motion=args.motion,
            batch_size=args.batch_size,
            resolution=args.resolution,
            mode=args.mode,
            stealth=args.stealth,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_animate_from_image(args: argparse.Namespace) -> None:
    """animate-from-image 커맨드를 처리합니다 (시작 / 시작+종료 / 시작+루프)."""
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
        if args.verbose:
            print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_extend_video(args: argparse.Namespace) -> None:
    """extend-video 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = client.extend_video(
            args.job_id,
            args.index,
            prompt=args.prompt or "",
            end_image=args.end_image,
            motion=args.motion,
            batch_size=args.batch_size,
            resolution=args.resolution,
            mode=args.mode,
            stealth=args.stealth,
        )
        if args.verbose:
            print(f"Job ID: {job.id}")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_download_video(args: argparse.Namespace) -> None:
    """download-video 커맨드를 처리합니다."""
    from midjourney_api.client import MidjourneyClient
    from midjourney_api.models import Job

    with MidjourneyClient(env_path=args.env, print_log=args.verbose) as client:
        job = Job(id=args.job_id, prompt="", status="completed",
                  user_id=client.user_id, event_type="video_diffusion")
        paths = client.download_video(job, output_dir=args.output, size=args.size, batch_size=args.batch_size)
        for p in paths:
            print(f"Saved: {p}")


def cmd_download(args: argparse.Namespace) -> None:
    """download 커맨드를 처리합니다."""
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
    p_imagine.add_argument("--iw", type=ImageWeight, help="Image weight 0-3 (default 1)")  # type: ignore[arg-type]
    p_imagine.add_argument("--ar", type=AspectRatio, help="Aspect ratio (e.g., 16:9)")  # type: ignore[arg-type]
    p_imagine.add_argument("-s", "--stylize", type=Stylize, help="0-1000")  # type: ignore[arg-type]
    p_imagine.add_argument("-c", "--chaos", type=Chaos, help="0-100")  # type: ignore[arg-type]
    p_imagine.add_argument("-q", "--quality", type=Quality, help="1, 2, or 4")  # type: ignore[arg-type]
    p_imagine.add_argument("--seed", type=Seed, help="0-4294967295")  # type: ignore[arg-type]
    p_imagine.add_argument("-w", "--weird", type=Weird, help="0-3000")  # type: ignore[arg-type]
    p_imagine.add_argument("--stop", type=Stop, help="10-100")  # type: ignore[arg-type]
    p_imagine.add_argument("--no", help="Negative prompt (comma separated)")
    p_imagine.add_argument("--tile", action="store_true", help="Enable tile mode")
    p_imagine.add_argument("--raw", action="store_true", help="Enable raw mode")
    p_imagine.add_argument("--draft", action="store_true", help="Enable draft mode")
    p_imagine.add_argument("--sref", help="Style reference (local file, URL, or code)")
    p_imagine.add_argument("--sw", type=StyleWeight, help="Style weight: 0-1000, default 100")  # type: ignore[arg-type]
    p_imagine.add_argument("--sv", type=StyleVersion, default=None,  # type: ignore[arg-type]
                           help="Style version: 4, 6, 7, 8 (sv=7+v7 omitted; sv=8 not yet supported)")
    p_imagine.add_argument("--oref", help="Object/character reference (local file or URL)")
    p_imagine.add_argument("--ow", type=OmniWeight, help="1-1000, default 100")  # type: ignore[arg-type]
    p_imagine.add_argument("-p", "--personalize", nargs="?", const="", default=None,
                           help="Personalization code (omit value for default)")
    p_imagine.add_argument("--niji", type=int, default=None, help="Niji model version (e.g. 7)")
    p_imagine.add_argument("-v", "--version", type=int, default=7,
                           help="Model version: 6 or 7 (default: 7)")
    p_imagine.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)  # type: ignore[arg-type]
    p_imagine.add_argument("--visibility", type=VisibilityMode, default=None)  # type: ignore[arg-type]
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

    # remix
    p_remix = sub.add_parser("remix", help="Remix an image with a new prompt")
    p_remix.add_argument("job_id", help="Parent job ID")
    p_remix.add_argument("index", type=int, help="Image index (0-3)")
    p_remix.add_argument("prompt", help="New prompt text (full prompt including parameters)")
    p_remix.add_argument("--subtle", action="store_true", help="Subtle remix (default: Strong)")
    p_remix.add_argument("--stealth", action="store_true", help="Generate in stealth mode")
    p_remix.add_argument("--mode", type=SpeedMode, default=SpeedMode.FAST)
    p_remix.add_argument("-o", "--output", default="./images", help="Output directory")
    p_remix.add_argument("--size", type=int, default=640, help="Image download size")

    # animate (i2v from imagine)
    p_animate = sub.add_parser("animate", help="Generate animation from an imagine job")
    p_animate.add_argument("job_id", help="Source imagine job ID")
    p_animate.add_argument("index", type=int, help="Image index (0-3)")
    p_animate.add_argument("-p", "--prompt", default="", help="Additional prompt text")
    p_animate.add_argument("--end-image", default=None, dest="end_image",
                           help="End frame (local file or URL); switches to start+end mode")
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
    p_ext.add_argument("-p", "--prompt", default=None, help="Text prompt to guide the extension")
    p_ext.add_argument("--end-image", default=None, dest="end_image",
                       help="End frame (local file, URL, or 'loop' for seamless loop)")
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
        "remix": cmd_remix,
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
