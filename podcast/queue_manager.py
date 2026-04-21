"""
Tracks which episodes have been published and what's queued next.
State saved per-novel at novels/<slug>/podcast/publish_queue.json
"""
from __future__ import annotations

import os
import re
import json
import mutagen
from datetime import datetime, timezone


def _queue_file(novel_dir: str) -> str:
    return os.path.join(novel_dir, "podcast", "publish_queue.json")


def _load(novel_dir: str) -> dict:
    path = _queue_file(novel_dir)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"published": [], "queued": [], "last_run": None}


def _save(state: dict, novel_dir: str):
    path = _queue_file(novel_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _extract_title_from_filename(mp3_filename: str) -> str | None:
    """Extract title from 'Chapter NNN - <title>.mp3' filenames."""
    m = re.match(r'Chapter \d+ - (.+)\.mp3$', mp3_filename)
    if m:
        return m.group(1)
    return None


def _read_chapter_title(voice_dir: str, mp3_filename: str) -> str | None:
    """Get chapter title: from filename first, then fall back to reading the .txt file."""
    title = _extract_title_from_filename(mp3_filename)
    if title:
        return title
    txt_name = mp3_filename.replace(".mp3", ".txt")
    novel_dir = os.path.dirname(os.path.dirname(os.path.abspath(voice_dir)))
    proofread_path = os.path.join(novel_dir, "proofread", txt_name)
    if os.path.exists(proofread_path):
        with open(proofread_path, encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line:
                return first_line
    return None


def build_queue(voice_dir: str, novel_title: str, novel_dir: str):
    """
    Scan voice_dir for all chapter mp3s and build the publish queue.
    Call this once after voice generation is complete.
    """
    state = _load(novel_dir)
    published_files = {ep["file"] for ep in state["published"]}

    mp3s = sorted([
        f for f in os.listdir(voice_dir)
        if f.endswith(".mp3") and (f.startswith("chapter-") or f.startswith("Chapter "))
    ])

    new_queued = []
    ep_num = len(state["published"]) + len(state["queued"]) + 1

    for mp3 in mp3s:
        if mp3 in published_files:
            continue
        if any(q["file"] == mp3 for q in state["queued"]):
            continue
        m = re.match(r'[Cc]hapter[-_ ](\d+)', mp3)
        chapter_num = int(m.group(1)) if m else ep_num
        chapter_title = _read_chapter_title(voice_dir, mp3)
        title = f"{novel_title} — {chapter_title}" if chapter_title else f"{novel_title} — Episode {ep_num} (Chapter {chapter_num})"
        new_queued.append({
            "file": mp3,
            "path": os.path.join(voice_dir, mp3),
            "episode": ep_num,
            "title": title,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        ep_num += 1

    state["queued"].extend(new_queued)
    _save(state, novel_dir)
    print(f"Queue built: {len(state['published'])} published, {len(state['queued'])} queued")
    return state


def get_next_batch(n: int, novel_dir: str) -> list:
    """Return the next N episodes from the queue without marking them published."""
    state = _load(novel_dir)
    return state["queued"][:n]


def mark_published(files: list[str], archive_urls: dict, novel_dir: str):
    """Mark a list of episode files as published with their Archive.org URLs."""
    state = _load(novel_dir)
    published_files = {ep["file"] for ep in state["published"]}

    newly_published = []
    remaining_queue = []

    for ep in state["queued"]:
        if ep["file"] in files and ep["file"] not in published_files:
            url = archive_urls.get(ep["file"], "")
            if not url:
                remaining_queue.append(ep)
                continue
            ep["published_at"] = datetime.now(timezone.utc).isoformat()
            ep["audio_url"] = url
            try:
                ep["file_size"] = os.path.getsize(ep["path"])
            except OSError:
                ep["file_size"] = 0
            try:
                audio = mutagen.File(ep["path"])
                ep["duration_seconds"] = int(audio.info.length) if audio else 0
            except Exception:
                ep["duration_seconds"] = 0
            state["published"].append(ep)
            newly_published.append(ep)
        else:
            remaining_queue.append(ep)

    state["queued"] = remaining_queue
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save(state, novel_dir)
    return newly_published
