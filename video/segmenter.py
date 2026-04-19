"""
Splits proofread chapters into ~5-minute narration segments (~750 words each).
Chapters shorter than 750 words are kept as a single segment.
Multiple short chapters can be combined into one segment.
"""

import os
from pipeline.config import SEGMENT_WORDS


def segment_chapters(proofread_dir: str) -> list[dict]:
    """
    Returns a list of segments. Each segment is:
    {
        "id": "seg-001",
        "chapters": ["chapter-001.txt", ...],
        "text": "...",
        "word_count": 742,
    }
    """
    chapters = sorted([
        f for f in os.listdir(proofread_dir)
        if (f.startswith("chapter-") or f.startswith("Chapter ")) and f.endswith(".txt")
    ])

    segments = []
    buffer_text = ""
    buffer_chapters = []
    seg_num = 1

    for ch in chapters:
        with open(os.path.join(proofread_dir, ch), encoding="utf-8") as f:
            text = f.read()

        words = len(text.split())

        # If adding this chapter would exceed segment limit, flush the buffer first
        if buffer_text and (len(buffer_text.split()) + words) > SEGMENT_WORDS:
            segments.append({
                "id": f"seg-{seg_num:03d}",
                "chapters": buffer_chapters[:],
                "text": buffer_text.strip(),
                "word_count": len(buffer_text.split()),
            })
            seg_num += 1
            buffer_text = ""
            buffer_chapters = []

        buffer_text += "\n\n" + text
        buffer_chapters.append(ch)

        # If this single chapter already exceeds the limit, flush immediately
        if len(buffer_text.split()) >= SEGMENT_WORDS:
            segments.append({
                "id": f"seg-{seg_num:03d}",
                "chapters": buffer_chapters[:],
                "text": buffer_text.strip(),
                "word_count": len(buffer_text.split()),
            })
            seg_num += 1
            buffer_text = ""
            buffer_chapters = []

    # Flush any remainder
    if buffer_text.strip():
        segments.append({
            "id": f"seg-{seg_num:03d}",
            "chapters": buffer_chapters[:],
            "text": buffer_text.strip(),
            "word_count": len(buffer_text.split()),
        })

    print(f"  {len(chapters)} chapters → {len(segments)} video segments (~5 min each)")
    return segments
