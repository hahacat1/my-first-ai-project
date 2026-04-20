"""
Splits raw beat/shot clips into 30-40 second YouTube Shorts / TikTok parts.
Groups 4-5 clips per part (each clip ~8 sec = 32-40 sec per part).
Converts to 9:16 vertical format with episode+part title overlay.
Output: video/shorts/episode-NNN-pt-PP.mp4
"""

from __future__ import annotations
import os
import re
import glob
import json

CLIPS_PER_PART = 4       # 4 × 8 sec = 32 sec (stays in 30-40 sec window)
CLIPS_MAX_PART = 5       # allow 5 if last group is short


def _episode_title(novel_title: str, chapter_num: int) -> str:
    return f"{novel_title} | Ep.{chapter_num}"


def split_episode(clips_dir: str, shorts_dir: str, chapter_num: int,
                  novel_title: str, bgm_path: str | None = None) -> list[str]:
    """
    Find all clips for chapter_num, group into 30-40 sec parts, render each.
    Returns list of output paths.
    """
    from shorts.formatter import make_short

    os.makedirs(shorts_dir, exist_ok=True)

    # Collect and sort clips for this chapter
    pattern = os.path.join(clips_dir, f"chapter-{chapter_num:03d}-beat-*-shot-*.mp4")
    all_clips = sorted(glob.glob(pattern), key=_clip_sort_key)

    if not all_clips:
        print(f"  [SHORTS] No clips found for chapter {chapter_num:03d}")
        return []

    # Group into parts
    groups = []
    for i in range(0, len(all_clips), CLIPS_PER_PART):
        group = all_clips[i:i + CLIPS_PER_PART]
        # Merge tiny last group into previous if only 1 clip
        if len(group) == 1 and groups:
            groups[-1].extend(group)
        else:
            groups.append(group)

    output_paths = []
    ep_label = _episode_title(novel_title, chapter_num)

    for part_num, clip_group in enumerate(groups, 1):
        out_name = f"episode-{chapter_num:03d}-pt-{part_num:02d}.mp4"
        out_path = os.path.join(shorts_dir, out_name)

        if os.path.exists(out_path):
            print(f"  [SHORTS] {out_name} already exists, skipping")
            output_paths.append(out_path)
            continue

        title = f"{ep_label} | Pt.{part_num}"
        print(f"  [SHORTS] {out_name} ({len(clip_group)} clips, ~{len(clip_group)*8}s)...",
              end=" ", flush=True)
        try:
            make_short(clip_group, out_path, title, bgm_path=bgm_path)
            print("done")
            output_paths.append(out_path)
        except Exception as e:
            print(f"FAILED: {e}")

    return output_paths


def split_all_episodes(clips_dir: str, shorts_dir: str, novel_title: str,
                       bgm_path: str | None = None) -> dict[int, list[str]]:
    """
    Process all chapters found in clips_dir.
    Returns {chapter_num: [part_paths]} dict.
    """
    progress_file = os.path.join(shorts_dir, ".progress.json")
    done: dict = json.load(open(progress_file)) if os.path.exists(progress_file) else {}

    # Discover chapter numbers from clip filenames
    all_clips = glob.glob(os.path.join(clips_dir, "chapter-*-beat-*-shot-*.mp4"))
    chapter_nums = sorted({
        int(m.group(1))
        for f in all_clips
        if (m := re.search(r'chapter-(\d+)-beat', os.path.basename(f)))
    })

    if not chapter_nums:
        print("  [SHORTS] No clips found. Run the video stage first.")
        return {}

    print(f"  [SHORTS] Splitting {len(chapter_nums)} chapters into parts...")
    results: dict[int, list[str]] = {}

    for ch_num in chapter_nums:
        if str(ch_num) in done:
            results[ch_num] = done[str(ch_num)]
            print(f"  [SHORTS] Chapter {ch_num:03d} already split ({len(done[str(ch_num)])} parts)")
            continue

        parts = split_episode(clips_dir, shorts_dir, ch_num, novel_title, bgm_path)
        results[ch_num] = parts
        done[str(ch_num)] = parts
        with open(progress_file, "w") as f:
            json.dump(done, f, indent=2)

    return results


def _clip_sort_key(path: str) -> tuple:
    """Sort chapter-NNN-beat-B-shot-S.mp4 numerically."""
    m = re.search(r'chapter-(\d+)-beat-(\d+)-shot-(\d+)', os.path.basename(path))
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (0, 0, 0)
