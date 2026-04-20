#!/usr/bin/env python3
"""
Podcast publisher — uploads batch to Archive.org, updates RSS, pushes to GitHub Pages.

Usage:
    python podcast/publisher.py --novel if-you-dont-become-the-main-character-youll-die --dump 10   # initial 10-episode dump
    python podcast/publisher.py --novel if-you-dont-become-the-main-character-youll-die --batch 1   # daily 1 episode

Run automatically at 8am via cron (set up with: python podcast/publisher.py --install-cron)
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import NOVELS
from podcast.queue_manager import build_queue, get_next_batch, mark_published
from podcast.archive_uploader import upload_episodes
from podcast.rss_generator import generate_rss


def publish_batch(novel_slug: str, n: int):
    novel = NOVELS[novel_slug]
    voice_dir = f"novels/{novel_slug}/voice"

    print(f"Building publish queue from: {voice_dir}")
    build_queue(voice_dir, novel["title"])

    batch = get_next_batch(n)
    if not batch:
        print("Nothing in queue — all episodes published or voice not generated yet.")
        return

    print(f"\nPublishing {len(batch)} episode(s):")
    for ep in batch:
        print(f"  {ep['file']} → {ep['title']}")

    # Upload to Archive.org
    print("\nUploading to Archive.org...")
    urls = upload_episodes(batch, novel_slug, novel["title"])

    if not urls:
        print("Upload failed — check Archive.org credentials (run: ia configure)")
        return

    # Mark as published
    mark_published([ep["file"] for ep in batch], urls)

    # Regenerate RSS feed
    print("\nUpdating RSS feed...")
    generate_rss()

    # Push to GitHub Pages
    print("\nPushing to GitHub Pages...")
    _push_github()

    print(f"\nDone! {len(urls)} episode(s) live on Spotify RSS feed.")


def _push_github():
    """Commit and push the updated docs/feed.xml to GitHub."""
    try:
        subprocess.run(["git", "add", "docs/feed.xml"], check=True)
        subprocess.run(["git", "commit", "-m", "chore: update podcast RSS feed"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("  RSS feed pushed to GitHub Pages.")
    except subprocess.CalledProcessError as e:
        print(f"  Git push failed: {e}")
        print("  Make sure the repo is connected to GitHub and GitHub Pages is enabled on /docs")


def install_cron():
    """Add 8am and 8pm EST cron jobs (runs at 12:00 and 00:00 UTC = 8am/8pm EDT)."""
    script_path = os.path.abspath(__file__)
    project_dir = os.path.dirname(os.path.dirname(script_path))
    base_cmd = (
        f"cd {project_dir} && "
        f"python3 {script_path} --novel if-you-dont-become-the-main-character-youll-die --batch 1 "
        f">> {project_dir}/podcast/cron.log 2>&1"
    )
    # 8am EDT = 12:00 UTC, 8pm EDT = 00:00 UTC
    cron_morning = f"0 12 * * * {base_cmd}"
    cron_evening = f"0 0 * * * {base_cmd}"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""

    if "publisher.py" in current:
        print("Cron jobs already installed.")
        return

    new_crontab = current.rstrip() + "\n" + cron_morning + "\n" + cron_evening + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
    print("Cron jobs installed! Will publish 1 episode at 8am EST and 1 at 8pm EST.")
    print(f"Log: {project_dir}/podcast/cron.log")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--novel", default="if-you-dont-become-the-main-character-youll-die")
    parser.add_argument("--dump", type=int, help="Initial dump: publish N episodes at once")
    parser.add_argument("--batch", type=int, default=2, help="Daily batch size (default: 2)")
    parser.add_argument("--install-cron", action="store_true", help="Install daily 8am cron job")
    args = parser.parse_args()

    if args.install_cron:
        install_cron()
        return

    n = args.dump if args.dump else args.batch
    publish_batch(args.novel, n)


if __name__ == "__main__":
    main()
