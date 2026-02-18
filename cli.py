#!/usr/bin/env python3
"""Command-line interface for Midjourney API client."""

from __future__ import annotations

import argparse
import sys


def cmd_login(args: argparse.Namespace) -> None:
    """Handle the login command."""
    from midjourney.client import MidjourneyClient

    client = MidjourneyClient(env_path=args.env)
    client.login()
    client.close()


def cmd_imagine(args: argparse.Namespace) -> None:
    """Handle the imagine command."""
    from midjourney.client import MidjourneyClient

    params = {}
    if args.ar:
        params["ar"] = args.ar
    if args.stylize is not None:
        params["s" if False else "stylize"] = args.stylize
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
    if args.tile:
        params["tile"] = True
    if args.raw:
        params["raw"] = True
    if args.draft:
        params["draft"] = True
    if args.sref:
        params["sref"] = args.sref
    if args.niji:
        params["niji"] = True

    with MidjourneyClient(env_path=args.env) as client:
        job = client.imagine(
            args.prompt,
            version=args.version,
            mode=args.mode,
            **params,
        )
        if job.is_completed and args.output:
            client.download_images(job, args.output, size=args.size)


def cmd_list(args: argparse.Namespace) -> None:
    """Handle the list command."""
    from midjourney.client import MidjourneyClient

    with MidjourneyClient(env_path=args.env) as client:
        jobs = client.list_jobs(limit=args.limit)
        for job in jobs:
            status_icon = {"completed": "+", "failed": "x", "running": "~"}.get(
                job.status, "?"
            )
            print(f"[{status_icon}] {job.id}  {job.prompt[:60]}")


def cmd_download(args: argparse.Namespace) -> None:
    """Handle the download command."""
    from midjourney.client import MidjourneyClient
    from midjourney.models import Job

    with MidjourneyClient(env_path=args.env) as client:
        job = Job(id=args.job_id, prompt="", status="completed", user_id=client.user_id)
        client.download_images(job, args.output, size=args.size)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Midjourney API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env", default=".env", help="Path to .env file")
    sub = parser.add_subparsers(dest="command", required=True)

    # login
    sub.add_parser("login", help="Login via browser (Playwright)")

    # imagine
    p_imagine = sub.add_parser("imagine", help="Generate images from a prompt")
    p_imagine.add_argument("prompt", help="Text prompt")
    p_imagine.add_argument("--ar", help="Aspect ratio (e.g., 16:9)")
    p_imagine.add_argument("-s", "--stylize", type=int, help="Stylize value (0-1000)")
    p_imagine.add_argument("-c", "--chaos", type=int, help="Chaos value (0-100)")
    p_imagine.add_argument("-q", "--quality", type=int, help="Quality (1, 2, or 4)")
    p_imagine.add_argument("--seed", type=int, help="Seed value")
    p_imagine.add_argument("-w", "--weird", type=int, help="Weird value (0-3000)")
    p_imagine.add_argument("--stop", type=int, help="Stop value (10-100)")
    p_imagine.add_argument("--no", help="Negative prompt (comma separated)")
    p_imagine.add_argument("--tile", action="store_true", help="Enable tile mode")
    p_imagine.add_argument("--raw", action="store_true", help="Enable raw mode")
    p_imagine.add_argument("--draft", action="store_true", help="Enable draft mode")
    p_imagine.add_argument("--sref", help="Style reference URL/code")
    p_imagine.add_argument("--niji", action="store_true", help="Use Niji mode")
    p_imagine.add_argument("-v", "--version", type=int, default=7, help="Model version")
    p_imagine.add_argument("--mode", default="fast", choices=["fast", "relax", "turbo"])
    p_imagine.add_argument("-o", "--output", default="./images", help="Output directory")
    p_imagine.add_argument("--size", type=int, default=640, help="Image download size")

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
        "list": cmd_list,
        "download": cmd_download,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
