"""
Tracks publish state across YouTube (full + Shorts) and TikTok.
State saved to novels/<slug>/publish_queue.json.

Schema:
{
  "episode-001": {
    "youtube_full":     "VIDEO_ID" | null,
    "youtube_shorts":   {"pt-01": "VIDEO_ID", ...},
    "tiktok_shorts":    {"pt-01": "VIDEO_ID", ...}
  }
}
"""

from __future__ import annotations
import json
import os


def _queue_path(novel_dir: str) -> str:
    return os.path.join(novel_dir, "publish_queue.json")


def load_queue(novel_dir: str) -> dict:
    path = _queue_path(novel_dir)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_queue(novel_dir: str, queue: dict) -> None:
    with open(_queue_path(novel_dir), "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def episode_key(chapter_num: int) -> str:
    return f"episode-{chapter_num:03d}"


def mark_youtube_full(novel_dir: str, chapter_num: int, video_id: str) -> None:
    queue = load_queue(novel_dir)
    key = episode_key(chapter_num)
    queue.setdefault(key, {})["youtube_full"] = video_id
    save_queue(novel_dir, queue)


def mark_youtube_short(novel_dir: str, chapter_num: int, part: str, video_id: str) -> None:
    queue = load_queue(novel_dir)
    key = episode_key(chapter_num)
    queue.setdefault(key, {}).setdefault("youtube_shorts", {})[part] = video_id
    save_queue(novel_dir, queue)


def mark_tiktok_short(novel_dir: str, chapter_num: int, part: str, video_id: str) -> None:
    queue = load_queue(novel_dir)
    key = episode_key(chapter_num)
    queue.setdefault(key, {}).setdefault("tiktok_shorts", {})[part] = video_id
    save_queue(novel_dir, queue)


def is_youtube_full_done(queue: dict, chapter_num: int) -> bool:
    return bool(queue.get(episode_key(chapter_num), {}).get("youtube_full"))


def is_youtube_short_done(queue: dict, chapter_num: int, part: str) -> bool:
    return bool(queue.get(episode_key(chapter_num), {}).get("youtube_shorts", {}).get(part))


def is_tiktok_short_done(queue: dict, chapter_num: int, part: str) -> bool:
    return bool(queue.get(episode_key(chapter_num), {}).get("tiktok_shorts", {}).get(part))
