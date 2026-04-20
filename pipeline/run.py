#!/usr/bin/env python3
"""
Master pipeline runner for webnovel content production.

Usage:
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages all
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages scrape,proofread
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages voice
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages images
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages video
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages shorts
    python pipeline/run.py --novel if-you-dont-become-the-main-character-youll-die --stages publish

Available stages: scrape, proofread, enrich, voice, images, video, shorts, publish, podcast
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import NOVELS

ALL_STAGES = ["scrape", "proofread", "enrich", "voice", "images", "batch", "video", "shorts", "publish", "podcast"]


def output_path(slug: str, *parts) -> str:
    base = os.path.join("novels", slug)
    return os.path.join(base, *parts) if parts else base


def run_scrape(novel: dict):
    slug = novel["slug"]
    scraper_name = novel["scraper"]
    dest = output_path(slug, "chapters")

    if scraper_name == "maplesantl":
        from scraper.sites.maplesantl import scrape_all, scrape_cover_image
        print(f"\n[SCRAPE] Downloading chapters to {dest}")
        scrape_all(dest)
        scrape_cover_image(output_path(slug))
    else:
        from scraper.downloader import download_novel
        from scraper.cleaner import clean_file
        from scraper.cover_scraper import scrape_cover
        import json
        os.makedirs(dest, exist_ok=True)
        meta = download_novel(novel["source_url"], output_path(slug, "_raw"))
        for i, raw in enumerate(meta["chapter_files"], 1):
            clean_file(raw, os.path.join(dest, f"chapter-{i:03d}.txt"))
        with open(os.path.join(dest, "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)
        scrape_cover(novel["source_url"], output_path(slug))


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
    chars_dir = output_path(slug, "characters")   # novels/<slug>/characters/<name>/
    scenes_dir = output_path(slug, "images", "scenes")

    print(f"\n[IMAGES] Extracting characters and generating images...")
    from images.character_extractor import extract_characters
    from images.sd_generator import generate_character_portraits
    from images.prompts import set_novel_style, DEFAULT_ART_STYLE

    # Apply novel-specific art style (e.g. soft shojo for female audience)
    set_novel_style(novel.get("art_style", DEFAULT_ART_STYLE))

    characters = extract_characters(proofread_dir, novel.get("characters", []))
    print(f"  Found {len(characters)} characters")
    print(f"  Review prompts in: {chars_dir}/<character_name>/prompt.txt before continuing")
    generate_character_portraits(characters, chars_dir)


def run_podcast(novel: dict, dump: int = 0, batch: int = 1):
    slug = novel["slug"]
    n = dump if dump > 0 else batch
    print(f"\n[PODCAST] Publishing {n} episode(s) for {novel['title']}")
    from podcast.publisher import publish_batch
    publish_batch(slug, n)


def run_batch(novel: dict):
    """
    Runs the director stage then exports a human-readable batch manifest
    (video/clips/batch_manifest.md) listing every clip that needs to be
    generated in Higgsfield manually.  No API calls are made.

    Workflow:
      1. python pipeline/run.py --novel <slug> --stages batch
      2. Open batch_manifest.md — one row per clip with filename + prompt
      3. Generate each clip in Higgsfield web UI, download, rename, drop in video/clips/
      4. python pipeline/run.py --novel <slug> --stages video  (assembles what's there)
    """
    slug = novel["slug"]
    proofread_dir = output_path(slug, "proofread")
    chars_dir = output_path(slug, "characters")
    novel_dir = output_path(slug)
    prompts_dir = output_path(slug, "video", "director_prompts")
    clips_dir = output_path(slug, "video", "clips")

    from video.segmenter import segment_chapters
    from video.director import write_director_prompts
    from video.composer import export_batch_manifest
    from video.character_mapper import load_characters, primary_character_for_segment

    chapters = segment_chapters(proofread_dir)
    characters = load_characters(novel_dir)

    primary_chars = {}
    if characters:
        for ch in chapters:
            portrait = primary_character_for_segment(ch["text"], characters, chars_dir)
            if portrait:
                primary_chars[ch["filename"]] = os.path.basename(os.path.dirname(portrait))

    chapters_with_beats = write_director_prompts(chapters, prompts_dir, primary_chars)
    export_batch_manifest(chapters_with_beats, clips_dir, chars_dir=chars_dir, novel_dir=novel_dir)


def run_video(novel: dict):
    slug = novel["slug"]
    proofread_dir = output_path(slug, "proofread")
    chars_dir = output_path(slug, "characters")
    novel_dir = output_path(slug)
    prompts_dir = output_path(slug, "video", "director_prompts")
    clips_dir = output_path(slug, "video", "clips")
    final_dir = output_path(slug, "video", "final")
    bgm_path = "assets/bgm.mp3"

    print(f"\n[VIDEO] Building episodes (1 chapter = 1 episode)...")
    from video.segmenter import segment_chapters
    from video.director import write_director_prompts
    from video.composer import compose_chapters
    from video.combiner import combine_to_episodes
    from video.soul_manager import ensure_souls
    from video.character_mapper import load_characters, primary_character_for_segment

    # Load chapters
    chapters = segment_chapters(proofread_dir)

    # Register Souls for key characters (one-time $3/character, skips existing)
    characters = load_characters(novel_dir)
    ensure_souls(characters, chars_dir, novel_dir)

    # Build character map: filename → primary character name
    primary_chars = {}
    if characters:
        for ch in chapters:
            portrait = primary_character_for_segment(ch["text"], characters, chars_dir)
            if portrait:
                primary_chars[ch["filename"]] = os.path.basename(os.path.dirname(portrait))

    # Generate storyboard prompts (cached per chapter, reviewable before generation)
    chapters_with_beats = write_director_prompts(chapters, prompts_dir, primary_chars)

    # Generate video clips (resumable — skips already-done clips)
    compose_chapters(chapters_with_beats, clips_dir, chars_dir=chars_dir, novel_dir=novel_dir)

    # Stitch clips into episodes with Ken Burns fill + BGM
    combine_to_episodes(clips_dir, final_dir, chars_dir=chars_dir, bgm_path=bgm_path)


def run_shorts(novel: dict):
    slug = novel["slug"]
    clips_dir = output_path(slug, "video", "clips")
    shorts_dir = output_path(slug, "video", "shorts")
    bgm_path = "assets/bgm.mp3"

    print(f"\n[SHORTS] Splitting clips into 30-40 sec YouTube Shorts / TikTok parts...")
    from shorts.splitter import split_all_episodes
    split_all_episodes(clips_dir, shorts_dir, novel["title"], bgm_path=bgm_path)
    print(f"  Shorts saved to: {shorts_dir}")


def run_publish(novel: dict):
    slug = novel["slug"]
    novel_dir = output_path(slug)
    final_dir = output_path(slug, "video", "final")
    shorts_dir = output_path(slug, "video", "shorts")

    import glob as _glob
    import re as _re
    from publish.queue_manager import (
        load_queue, is_youtube_full_done, is_youtube_short_done, is_tiktok_short_done,
        mark_youtube_full, mark_youtube_short, mark_tiktok_short
    )
    from publish.youtube_uploader import upload_episode, upload_short
    from publish.tiktok_uploader import upload_video as tiktok_upload
    from pipeline.config import PUBLISH_FULL_PER_RUN, PUBLISH_SHORTS_PER_RUN

    queue = load_queue(novel_dir)
    novel_title = novel["title"]

    # --- Full episodes → YouTube ---
    full_eps = sorted(_glob.glob(os.path.join(final_dir, "episode-*.mp4")))
    uploaded_full = 0
    for ep_path in full_eps:
        if uploaded_full >= PUBLISH_FULL_PER_RUN:
            break
        m = _re.search(r'episode-(\d+)', os.path.basename(ep_path))
        if not m:
            continue
        ch_num = int(m.group(1))
        if is_youtube_full_done(queue, ch_num):
            continue
        ep_num = ch_num
        title = f"{novel_title} — Episode {ep_num}"
        desc = (f"Episode {ep_num} of '{novel_title}' — AI-animated Korean web novel.\n"
                f"Subscribe for daily episodes!\n\n#Anime #WebNovel #Manhwa #KoreanNovel")
        try:
            vid_id = upload_episode(ep_path, title, desc)
            mark_youtube_full(novel_dir, ch_num, vid_id)
            queue = load_queue(novel_dir)
            uploaded_full += 1
        except Exception as e:
            print(f"  [PUBLISH] YouTube full upload failed for ep {ch_num}: {e}")

    # --- Shorts → YouTube Shorts + TikTok ---
    short_files = sorted(_glob.glob(os.path.join(shorts_dir, "episode-*-pt-*.mp4")))
    uploaded_shorts = 0
    for short_path in short_files:
        if uploaded_shorts >= PUBLISH_SHORTS_PER_RUN:
            break
        m = _re.search(r'episode-(\d+)-pt-(\d+)', os.path.basename(short_path))
        if not m:
            continue
        ch_num, pt_num = int(m.group(1)), int(m.group(2))
        part_key = f"pt-{pt_num:02d}"
        title = f"{novel_title} Ep.{ch_num} Pt.{pt_num}"
        desc = f"Part {pt_num} of Episode {ch_num} | '{novel_title}'"

        yt_done = is_youtube_short_done(queue, ch_num, part_key)
        tt_done = is_tiktok_short_done(queue, ch_num, part_key)

        if not yt_done:
            try:
                vid_id = upload_short(short_path, title, desc)
                mark_youtube_short(novel_dir, ch_num, part_key, vid_id)
                queue = load_queue(novel_dir)
            except Exception as e:
                print(f"  [PUBLISH] YouTube Short upload failed {short_path}: {e}")

        if not tt_done:
            try:
                pub_id = tiktok_upload(short_path, title, desc)
                mark_tiktok_short(novel_dir, ch_num, part_key, pub_id)
                queue = load_queue(novel_dir)
            except Exception as e:
                print(f"  [PUBLISH] TikTok upload failed {short_path}: {e}")

        if not yt_done or not tt_done:
            uploaded_shorts += 1

    print(f"\n[PUBLISH] Done — {uploaded_full} full episode(s), {uploaded_shorts} short(s) published.")


STAGE_RUNNERS = {
    "scrape": run_scrape,
    "proofread": run_proofread,
    "enrich": run_enrich,
    "voice": run_voice,
    "images": run_images,
    "batch": run_batch,
    "video": run_video,
    "shorts": run_shorts,
    "publish": run_publish,
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
    parser.add_argument("--batch", type=int, default=2,
                        help="Podcast: publish N episodes (daily drip, default 2)")
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
