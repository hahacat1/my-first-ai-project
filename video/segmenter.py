"""
Loads each proofread chapter as one video unit (1 chapter = 1 episode).
No word-count splitting — chapter boundaries are preserved for the storyboard approach.
"""

from __future__ import annotations
import os


def segment_chapters(proofread_dir: str) -> list[dict]:
    """
    Returns one dict per chapter file:
    {
        "filename": "Chapter 001 - Title.txt",
        "text": "...",
        "word_count": 1234,
    }
    """
    chapter_files = sorted([
        f for f in os.listdir(proofread_dir)
        if (f.startswith("chapter-") or f.startswith("Chapter ")) and f.endswith(".txt")
    ])

    chapters = []
    for f in chapter_files:
        with open(os.path.join(proofread_dir, f), encoding="utf-8") as fh:
            text = fh.read()
        chapters.append({
            "filename": f,
            "text": text.strip(),
            "word_count": len(text.split()),
        })

    print(f"  Loaded {len(chapters)} chapters (1 chapter = 1 episode)")
    return chapters
