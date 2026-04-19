"""
Tracks which episodes have been published and what's queued next.
Saves state to podcast/publish_queue.json
"""

import os
import json
from datetime import datetime, timezone

QUEUE_FILE = "podcast/publish_queue.json"


def _load() -> dict:
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return {"published": [], "queued": [], "last_run": None}


def _save(state: dict):
    os.makedirs("podcast", exist_ok=True)
    with open(QUEUE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def build_queue(voice_dir: str, novel_title: str):
    """
    Scan voice_dir for all chapter mp3s and build the publish queue.
    Call this once after voice generation is complete.
    """
    state = _load()
    published_files = {ep["file"] for ep in state["published"]}

    mp3s = sorted([
        f for f in os.listdir(voice_dir)
        if f.endswith(".mp3") and f.startswith("chapter-")
    ])

    new_queued = []
    ep_num = len(state["published"]) + len(state["queued"]) + 1

    for mp3 in mp3s:
        if mp3 in published_files:
            continue
        if any(q["file"] == mp3 for q in state["queued"]):
            continue
        chapter_num = int(mp3.replace("chapter-", "").replace(".mp3", ""))
        new_queued.append({
            "file": mp3,
            "path": os.path.join(voice_dir, mp3),
            "episode": ep_num,
            "title": f"{novel_title} — Episode {ep_num} (Chapter {chapter_num})",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        ep_num += 1

    state["queued"].extend(new_queued)
    _save(state)
    print(f"Queue built: {len(state['published'])} published, {len(state['queued'])} queued")
    return state


def get_next_batch(n: int) -> list:
    """Return the next N episodes from the queue without marking them published."""
    state = _load()
    return state["queued"][:n]


def mark_published(files: list[str], archive_urls: dict):
    """Mark a list of episode files as published with their Archive.org URLs."""
    state = _load()
    published_files = {ep["file"] for ep in state["published"]}

    newly_published = []
    remaining_queue = []

    for ep in state["queued"]:
        if ep["file"] in files and ep["file"] not in published_files:
            ep["published_at"] = datetime.now(timezone.utc).isoformat()
            ep["audio_url"] = archive_urls.get(ep["file"], "")
            state["published"].append(ep)
            newly_published.append(ep)
        else:
            remaining_queue.append(ep)

    state["queued"] = remaining_queue
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save(state)
    return newly_published
