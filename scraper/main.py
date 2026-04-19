#!/usr/bin/env python3
"""
Webnovel Scraper — Stage 1 of the AI content pipeline.

Usage:
    python scraper/main.py --url <novel-url> --output ./output

Supported:
    - maplesantl.com     → custom scraper (scraper/sites/maplesantl.py)
    - All other sites    → lightnovel-crawler (lncrawl)
"""

import argparse
import os
import sys

# Allow running from project root: python scraper/main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_args():
    parser = argparse.ArgumentParser(description="Download and clean webnovel chapters.")
    parser.add_argument("--url", required=True, help="Full URL of the novel")
    parser.add_argument("--output", default="./output", help="Directory to save chapters (default: ./output)")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  Webnovel Scraper")
    print("=" * 60)

    if "maplesantl.com" in args.url or "maplesan9.wordpress.com" in args.url:
        _run_maplesantl(args.output)
    else:
        _run_lncrawl(args.url, args.output)


def _run_maplesantl(output_dir: str):
    from scraper.sites.maplesantl import scrape_all

    novel_dir = os.path.join(output_dir, "if-you-dont-become-the-main-character-youll-die")
    print(f"\nUsing custom scraper for maplesantl.com")
    print(f"Saving to: {novel_dir}\n")

    meta = scrape_all(novel_dir)

    print(f"\nDone! {meta['chapter_count']} chapters saved to: {meta['output_dir']}")


def _run_lncrawl(url: str, output_dir: str):
    import json
    from scraper.downloader import download_novel
    from scraper.cleaner import clean_file

    try:
        meta = download_novel(url, output_dir)
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    print(f"\nFound {meta['chapter_count']} chapters for: {meta['title']}")

    novel_dir = os.path.join(output_dir, meta["title"])
    os.makedirs(novel_dir, exist_ok=True)
    print(f"Cleaning and saving chapters to: {novel_dir}\n")

    for i, raw_path in enumerate(meta["chapter_files"], start=1):
        out_path = os.path.join(novel_dir, f"chapter-{i:03d}.txt")
        clean_file(raw_path, out_path)
        print(f"  [{i}/{meta['chapter_count']}] chapter-{i:03d}.txt")

    metadata = {
        "title": meta["title"],
        "source_url": meta["source_url"],
        "chapter_count": meta["chapter_count"],
        "output_dir": novel_dir,
    }
    meta_path = os.path.join(novel_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nDone! {meta['chapter_count']} chapters saved to: {novel_dir}")


if __name__ == "__main__":
    main()
