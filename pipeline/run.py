#!/usr/bin/env python3
"""
Master pipeline runner for webnovel content production.

Usage:
    python pipeline/run.py --novel if-you-dont-become-mc --stages all
    python pipeline/run.py --novel if-you-dont-become-mc --stages scrape,proofread
    python pipeline/run.py --novel if-you-dont-become-mc --stages voice
    python pipeline/run.py --novel if-you-dont-become-mc --stages images
    python pipeline/run.py --novel if-you-dont-become-mc --stages video

Available stages: scrape, proofread, enrich, voice, images, video, podcast
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import NOVELS

ALL_STAGES = ["scrape", "proofread", "enrich", "voice", "images", "video", "podcast"]


def output_path(slug: str, *parts) -> str:
    base = os.path.join("output", slug)
    return os.path.join(base, *parts) if parts else base


def run_scrape(novel: dict):
    slug = novel["slug"]
    scraper_name = novel["scraper"]
    dest = output_path(slug, "chapters")

    if scraper_name == "maplesantl":
        from scraper.sites.maplesantl import scrape_all
        print(f"\n[SCRAPE] Downloading chapters to {dest}")
        scrape_all(dest)
    else:
        from scraper.downloader import download_novel
        from scraper.cleaner import clean_file
        import json
        os.makedirs(dest, exist_ok=True)
        meta = download_novel(novel["source_url"], output_path(slug, "_raw"))
        for i, raw in enumerate(meta["chapter_files"], 1):
            clean_file(raw, os.path.join(dest, f"chapter-{i:03d}.txt"))
        with open(os.path.join(dest, "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)


def run_proofread(novel: dict):
    slug = novel["slug"]
    in_dir = output_path(slug, "chapters")
    out_dir = output_path(slug, "proofread")

    sys.argv = ["proofread.py"]  # reset args for the module
    import importlib.util, types

    print(f"\n[PROOFREAD] {in_dir} → {out_dir}")

    # Call proofreader directly
    from proofreader.proofread import get_chapter_files, proofread_chapter, load_progress, save_progress
    import time

    os.makedirs(out_dir, exist_ok=True)

    # Temporarily patch INPUT_DIR / OUTPUT_DIR
    import proofreader.proofread as pr_mod
    original_in = pr_mod.INPUT_DIR
    original_out = pr_mod.OUTPUT_DIR
    pr_mod.INPUT_DIR = in_dir
    pr_mod.OUTPUT_DIR = out_dir

    chapters = get_chapter_files()
    done = load_progress()
    remaining = [c for c in chapters if c not in done]

    print(f"  {len(remaining)} chapters to proofread...")

    times = []
    for i, filename in enumerate(remaining, 1):
        in_path = os.path.join(in_dir, filename)
        out_path_f = os.path.join(out_dir, filename)
        with open(in_path, encoding="utf-8") as f:
            original = f.read()

        print(f"  [{i}/{len(remaining)}] {filename}...", end=" ", flush=True)
        t0 = time.time()
        corrected = proofread_chapter(original)
        with open(out_path_f, "w", encoding="utf-8") as f:
            f.write(corrected)
        elapsed = time.time() - t0
        times.append(elapsed)
        avg = sum(times) / len(times)
        eta = (len(remaining) - i) * avg / 60
        print(f"done ({elapsed:.0f}s) — ETA: {eta:.0f}m")
        done.add(filename)
        save_progress(done)

    pr_mod.INPUT_DIR = original_in
    pr_mod.OUTPUT_DIR = original_out
    print(f"  Proofread complete: {out_dir}")


def run_enrich(novel: dict):
    slug = novel["slug"]
    proofread_dir = output_path(slug, "proofread")
    voice_dir = output_path(slug, "voice")

    print(f"\n[ENRICH] Generating subtitles for bare titles in {proofread_dir}")
    from proofreader.enrich_titles import run as enrich_run
    enrich_run(proofread_dir=proofread_dir, voice_dir=voice_dir)


def run_voice(novel: dict):
    slug = novel["slug"]
    in_dir = output_path(slug, "proofread")
    out_dir = output_path(slug, "voice")

    print(f"\n[VOICE] {in_dir} → {out_dir}")
    from voice.tts import generate_all
    generate_all(in_dir, out_dir)


def run_images(novel: dict):
    slug = novel["slug"]
    proofread_dir = output_path(slug, "proofread")
    chars_dir = output_path(slug, "images", "characters")
    scenes_dir = output_path(slug, "images", "scenes")

    print(f"\n[IMAGES] Extracting characters and generating images...")
    from images.character_extractor import extract_characters
    from images.sd_generator import generate_character_portraits, generate_scene_images

    characters = extract_characters(proofread_dir, novel.get("characters", []))
    print(f"  Found {len(characters)} characters")
    generate_character_portraits(characters, chars_dir)
    generate_scene_images(proofread_dir, scenes_dir)


def run_podcast(novel: dict, dump: int = 0, batch: int = 1):
    slug = novel["slug"]
    n = dump if dump > 0 else batch
    print(f"\n[PODCAST] Publishing {n} episode(s) for {novel['title']}")
    from podcast.publisher import publish_batch
    publish_batch(slug, n)


def run_video(novel: dict):
    slug = novel["slug"]
    proofread_dir = output_path(slug, "proofread")
    voice_dir = output_path(slug, "voice")
    scenes_dir = output_path(slug, "images", "scenes")
    segments_dir = output_path(slug, "video", "segments")
    final_dir = output_path(slug, "video", "final")

    print(f"\n[VIDEO] Building video segments...")
    from video.segmenter import segment_chapters
    from video.director import write_director_prompts
    from video.composer import compose_segments
    from video.combiner import combine_to_episodes

    segments = segment_chapters(proofread_dir)
    prompts = write_director_prompts(segments, scenes_dir)
    compose_segments(prompts, scenes_dir, voice_dir, segments_dir)
    combine_to_episodes(segments_dir, final_dir)


STAGE_RUNNERS = {
    "scrape": run_scrape,
    "proofread": run_proofread,
    "enrich": run_enrich,
    "voice": run_voice,
    "images": run_images,
    "video": run_video,
    "podcast": run_podcast,
}


def main():
    parser = argparse.ArgumentParser(description="Webnovel AI content pipeline")
    parser.add_argument("--novel", required=True, choices=list(NOVELS.keys()),
                        help="Novel slug from pipeline/config.py")
    parser.add_argument("--stages", default="all",
                        help="Comma-separated stages or 'all': scrape,proofread,enrich,voice,images,video,podcast")
    parser.add_argument("--dump", type=int, default=0,
                        help="Podcast: publish first N episodes in one batch (initial dump)")
    parser.add_argument("--batch", type=int, default=1,
                        help="Podcast: publish N episodes (daily drip, default 1)")
    args = parser.parse_args()

    novel = NOVELS[args.novel]
    stages = ALL_STAGES if args.stages == "all" else [s.strip() for s in args.stages.split(",")]

    print("=" * 60)
    print(f"  Novel: {novel['title']}")
    print(f"  Stages: {', '.join(stages)}")
    print("=" * 60)

    os.makedirs(output_path(novel["slug"]), exist_ok=True)

    for stage in stages:
        if stage not in STAGE_RUNNERS:
            print(f"Unknown stage: {stage}. Valid: {', '.join(ALL_STAGES)}")
            sys.exit(1)
        if stage == "podcast":
            STAGE_RUNNERS[stage](novel, dump=args.dump, batch=args.batch)
        else:
            STAGE_RUNNERS[stage](novel)

    print("\nPipeline complete!")


if __name__ == "__main__":
    main()
