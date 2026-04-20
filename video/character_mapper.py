"""
Maps segment text to the most relevant character portrait for video generation.
Uses simple name-frequency counting — no LLM needed, runs instantly.
"""

from __future__ import annotations
import json
import os


def load_characters(novel_dir: str) -> list[dict]:
    """Load characters.json from the novel directory."""
    path = os.path.join(novel_dir, "characters.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def primary_character_for_segment(
    segment_text: str,
    characters: list[dict],
    chars_dir: str,
) -> str | None:
    """
    Count how many times each character's name appears in segment_text.
    Return the portrait.png path for the most-mentioned character whose portrait exists.
    Falls back to 'protagonist' folder if nothing matches.
    Returns None if no portrait found at all.
    """
    text_lower = segment_text.lower()
    best_name = None
    best_count = 0

    for char in characters:
        name = char.get("name", "")
        if not name or len(name) < 3:
            continue
        count = text_lower.count(name.lower())
        if count > best_count:
            name_slug = name.lower().replace(" ", "_").replace("/", "_")
            portrait = os.path.join(chars_dir, name_slug, "portrait.png")
            if os.path.exists(portrait):
                best_count = count
                best_name = name_slug

    if best_name:
        return os.path.join(chars_dir, best_name, "portrait.png")

    # Fallback: protagonist
    fallback = os.path.join(chars_dir, "protagonist", "portrait.png")
    if os.path.exists(fallback):
        return fallback

    return None
