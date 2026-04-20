"""
Calls Higgsfield API to generate video clips from storyboard beat/shot prompts.
Each chapter produces N beats × 4 shots = ~20-28 clips saved to out_dir.

Generation flow per shot:
  If SoulID available → soul_to_keyframe(soul_id, prompt) → image_to_video(keyframe, prompt)
  Fallback            → image_to_video(portrait.png, prompt)

Model is configurable via VIDEO_MODEL in pipeline/config.py (default: seedream-5.0-lite).
"""

from __future__ import annotations
import os
import re
import time
import json
import tempfile
import requests
from pipeline.config import HIGGSFIELD_API_KEY, VIDEO_MODEL

HIGGSFIELD_API = "https://api.higgsfield.ai/v1"


def _auth() -> dict:
    if not HIGGSFIELD_API_KEY:
        raise RuntimeError(
            "Higgsfield API key not set. Add HIGGSFIELD_API_KEY to .env"
        )
    return {"Authorization": f"Bearer {HIGGSFIELD_API_KEY}"}


def _upload_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{HIGGSFIELD_API}/upload",
            headers=_auth(),
            files={"file": f},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["url"]


def _upload_bytes(data: bytes, suffix: str = ".png") -> str:
    """Upload raw image bytes (e.g. from soul_to_keyframe) and return URL."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        url = _upload_image(tmp_path)
    finally:
        os.unlink(tmp_path)
    return url


def _image_to_video(image_url: str, prompt: str, duration: int = 8) -> bytes:
    """Submit image-to-video job, poll until done, return video bytes."""
    resp = requests.post(
        f"{HIGGSFIELD_API}/video/generate",
        headers={**_auth(), "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "image_url": image_url,
            "duration": duration,
            "model": VIDEO_MODEL,
        },
        timeout=30,
    )
    resp.raise_for_status()
    job_id = resp.json()["id"]

    for _ in range(180):
        time.sleep(5)
        data = requests.get(f"{HIGGSFIELD_API}/video/{job_id}", headers=_auth(), timeout=15).json()
        status = data.get("status")
        if status == "completed":
            return requests.get(data["output_url"], timeout=120).content
        elif status == "failed":
            raise RuntimeError(f"Higgsfield job failed: {data.get('error', 'unknown')}")

    raise RuntimeError(f"Higgsfield job timed out: {job_id}")


def _build_chapter_portrait_map(chapters: list[dict], chars_dir: str,
                                novel_dir: str) -> dict[str, tuple[str | None, str | None]]:
    """Returns {filename: (portrait_path, soul_id)} for each chapter."""
    from video.character_mapper import load_characters, primary_character_for_segment
    from video.soul_manager import load_souls

    characters = load_characters(novel_dir) if novel_dir else []
    souls = load_souls(novel_dir) if novel_dir else {}
    result = {}
    for ch in chapters:
        portrait_path = None
        soul_id = None
        if chars_dir and characters:
            portrait = primary_character_for_segment(ch["text"], characters, chars_dir)
            if portrait:
                portrait_path = portrait
                char_name = os.path.basename(os.path.dirname(portrait))
                soul_id = souls.get(char_name)
        result[ch["filename"]] = (portrait_path, soul_id)
    return result


def _find_scene_image(ch_num: int, novel_dir: str) -> str | None:
    """Return path to the scene image for this chapter, or None if not found."""
    import glob as _glob
    scenes_dir = os.path.join(novel_dir, "images", "scenes")
    pattern = os.path.join(scenes_dir, f"Chapter {ch_num:03d} - *.png")
    matches = _glob.glob(pattern)
    return matches[0] if matches else None


def export_batch_manifest(chapters: list[dict], out_dir: str,
                          chars_dir: str = "", novel_dir: str = "") -> str:
    """
    Export a human-readable batch manifest (Markdown) listing every clip that
    needs to be generated in Higgsfield.  No API calls are made.

    Workflow:
      1. Open each chapter-NNN/ folder in video/batch/
      2. Upload portrait.png to Higgsfield → Image-to-Video
      3. Paste each prompt, generate (8 sec), download
      4. Rename to the filename shown, drop in video/clips/
      5. Re-run --stages video — clips already present are skipped
    """
    import shutil

    os.makedirs(out_dir, exist_ok=True)
    batch_dir = os.path.join(os.path.dirname(out_dir), "batch")
    os.makedirs(batch_dir, exist_ok=True)

    portrait_map = _build_chapter_portrait_map(chapters, chars_dir, novel_dir)

    total = sum(len(b["shots"]) for ch in chapters for b in ch.get("beats", []))
    already_done = 0

    readme_lines = [
        "# Higgsfield Batch — Shot Prompts",
        "",
        "## Workflow",
        "1. Open a `chapter-NNN/` folder",
        "2. Upload `portrait.png` to Higgsfield → Image-to-Video (8 sec, Seedream model)",
        "3. Paste each prompt, generate, download",
        f"4. Rename to the filename shown and drop in `{os.path.abspath(out_dir)}/`",
        "5. Re-run `--stages video` — files already present are skipped automatically",
        "",
        "---",
        "",
        "| Chapter | Clip | Beat | Prompt |",
        "|---------|------|------|--------|",
    ]

    for ch in chapters:
        filename = ch["filename"]
        beats = ch.get("beats", [])
        if not beats:
            continue
        m = re.search(r'(\d+)', filename)
        ch_num = int(m.group(1)) if m else 0
        portrait_path, _ = portrait_map.get(filename, (None, None))

        # Per-chapter folder with portrait copy
        ch_dir = os.path.join(batch_dir, f"chapter-{ch_num:03d}")
        os.makedirs(ch_dir, exist_ok=True)

        if portrait_path and os.path.exists(portrait_path):
            dest = os.path.join(ch_dir, "portrait.png")
            if not os.path.exists(dest):
                shutil.copy2(portrait_path, dest)
            char_label = os.path.basename(os.path.dirname(portrait_path))
        else:
            char_label = "unknown"

        # Copy scene image if available
        scene_img_src = _find_scene_image(ch_num, novel_dir)
        if scene_img_src:
            dest_scene = os.path.join(ch_dir, "scene.png")
            if not os.path.exists(dest_scene):
                shutil.copy2(scene_img_src, dest_scene)
            scene_line = "**Scene image:** `scene.png` (in this folder — visual reference)"
        else:
            scene_line = "**Scene image:** _(not generated yet — run `--stages images` first)_"

        synopsis = ch.get("synopsis", "")
        synopsis_block = (
            f"\n## Episode Synopsis\n\n{synopsis}\n"
            if synopsis else
            "\n## Episode Synopsis\n\n_(synopsis not available — re-run `--stages batch`)_\n"
        )

        ch_lines = [
            f"# Chapter {ch_num:03d} — {filename.replace('.txt', '')}",
            "",
            f"**Character:** {char_label}  |  Upload `portrait.png` to Higgsfield",
            scene_line,
            f"**Drop clips in:** `{os.path.abspath(out_dir)}/`",
            synopsis_block,
            "---",
            "",
        ]
        shot_labels = ["Wide", "Medium", "Close-up", "Cutaway"]

        for b_idx, beat in enumerate(beats, 1):
            ch_lines += [f"## Beat {b_idx}: {beat['beat']}", ""]
            for s_idx, shot_prompt in enumerate(beat["shots"], 1):
                clip_name = f"chapter-{ch_num:03d}-beat-{b_idx}-shot-{s_idx}.mp4"
                exists = os.path.exists(os.path.join(out_dir, clip_name))
                already_done += int(exists)
                status = "✅ done" if exists else "☐ todo"
                label = shot_labels[s_idx - 1] if s_idx <= 4 else f"Shot {s_idx}"
                ch_lines += [
                    f"**{label} — `{clip_name}`** {status}",
                    f"> {shot_prompt}",
                    "",
                ]
                prompt_esc = shot_prompt.replace("|", "\\|")
                readme_lines.append(
                    f"| {ch_num:03d} | `{clip_name}` | {beat['beat'][:50]} | {prompt_esc} |"
                )

        with open(os.path.join(ch_dir, "prompts.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(ch_lines))

    readme_lines += ["", "---", f"*{already_done} of {total} clips already generated.*"]
    with open(os.path.join(batch_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme_lines))

    print(f"\n  Batch folder: {batch_dir}")
    print(f"  {len(chapters)} chapter folders with portrait + prompts.md")
    print(f"  {total - already_done} clips remaining out of {total} total")
    return batch_dir


def compose_chapters(chapters: list[dict], out_dir: str,
                     chars_dir: str = "", novel_dir: str = "") -> None:
    """
    For each chapter: generate video clips for every beat × shot via Higgsfield API.
    Saves clips to out_dir/chapter-NNN-beat-B-shot-S.mp4
    Skips clips that already exist on disk (manual downloads work automatically).
    Progress also tracked in out_dir/.progress.json for API-generated clips.
    """
    from video.soul_manager import soul_to_keyframe

    os.makedirs(out_dir, exist_ok=True)

    portrait_map = _build_chapter_portrait_map(chapters, chars_dir, novel_dir)

    progress_file = os.path.join(out_dir, ".progress.json")
    done = set(json.load(open(progress_file)) if os.path.exists(progress_file) else [])

    total_shots = sum(len(b["shots"]) for ch in chapters for b in ch.get("beats", []))
    print(f"  Generating clips for {len(chapters)} chapters "
          f"({total_shots} total shots) via Higgsfield [{VIDEO_MODEL}]...")

    for ch in chapters:
        filename = ch["filename"]
        beats = ch.get("beats", [])
        if not beats:
            print(f"  {filename} — no beats, skipping (run director stage first)")
            continue

        portrait_path, soul_id = portrait_map.get(filename, (None, None))

        m = re.search(r'(\d+)', filename)
        ch_num = int(m.group(1)) if m else 0

        for b_idx, beat in enumerate(beats, 1):
            for s_idx, shot_prompt in enumerate(beat["shots"], 1):
                clip_name = f"chapter-{ch_num:03d}-beat-{b_idx}-shot-{s_idx}.mp4"
                out_path = os.path.join(out_dir, clip_name)

                # Skip if already on disk (manual download or prior API run)
                if os.path.exists(out_path):
                    done.add(clip_name)
                    continue
                if clip_name in done:
                    continue

                label = f"ch{ch_num:03d} beat{b_idx} shot{s_idx}"
                print(f"    {label}...", end=" ", flush=True)

                try:
                    _soul_id = soul_id  # local so we can null it on failure
                    if _soul_id:
                        try:
                            keyframe_bytes = soul_to_keyframe(_soul_id, shot_prompt)
                            image_url = _upload_bytes(keyframe_bytes)
                            print(f"[soul]", end=" ", flush=True)
                        except Exception as e:
                            print(f"[soul failed: {e}, using portrait]", end=" ", flush=True)
                            _soul_id = None

                    if not _soul_id:
                        if portrait_path:
                            image_url = _upload_image(portrait_path)
                        else:
                            print("no image — skipping")
                            continue

                    video_bytes = _image_to_video(image_url, shot_prompt)
                    with open(out_path, "wb") as f:
                        f.write(video_bytes)
                    print(f"done ({len(video_bytes) // 1024} KB)")
                    done.add(clip_name)
                    with open(progress_file, "w") as f:
                        json.dump(sorted(done), f)

                except RuntimeError as e:
                    print(f"FAILED: {e}")
                    if "API key" in str(e):
                        return
