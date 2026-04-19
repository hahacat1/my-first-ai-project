#!/usr/bin/env python3
"""
Post-proofreading step: generates subtitles for bare "Episode N" chapters,
updates the title line in each file, then renames:
  chapter-NNN.txt  →  Chapter NNN - Episode N: The Real Title.txt

Also renames matching mp3s in the voice dir if they exist.

Run AFTER proofreading is complete:
    python3 proofreader/enrich_titles.py
    python3 proofreader/enrich_titles.py --dry-run   # preview only
"""

import argparse
import os
import re
from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

PROOFREAD_DIR = "output/proofread"
VOICE_DIR = None  # set via CLI --voice-dir or pipeline call; mp3 rename is skipped if None
MODEL = LM_STUDIO_MODEL

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

_BARE_TITLE = re.compile(r'^Episode \d+$', re.IGNORECASE)
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\n\r]')


def _sanitize(title: str) -> str:
    return _INVALID_CHARS.sub('', title).strip().rstrip('.')


def _generate_subtitle(body: str) -> str:
    """Ask the LLM for a 4-6 word subtitle based on the chapter body."""
    snippet = body[:1500]
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content":
            "Give me a 4-6 word subtitle for this web novel chapter. "
            "Reply with ONLY the subtitle words, no quotes, no punctuation at the end.\n\n"
            f"{snippet}"}],
        temperature=0.3,
        max_tokens=20,
    )
    return response.choices[0].message.content.strip().strip('"\'')


def enrich_title(chapter_num: int, text: str) -> tuple[str, str]:
    """
    Returns (display_title, updated_text).
    If title is bare, generates subtitle and injects it back into line 1.
    """
    lines = text.splitlines()
    first_line = lines[0].strip() if lines else f"Episode {chapter_num}"

    if _BARE_TITLE.match(first_line):
        body = "\n".join(lines[1:]).strip()
        subtitle = _generate_subtitle(body)
        display_title = f"{first_line}: {subtitle}"
        lines[0] = display_title
        updated_text = "\n".join(lines)
        return display_title, updated_text

    return first_line, text


def run(dry_run: bool = False,
        proofread_dir: str = PROOFREAD_DIR,
        voice_dir: str | None = VOICE_DIR) -> None:
    files = sorted(
        f for f in os.listdir(proofread_dir)
        if f.startswith("chapter-") and f.endswith(".txt")
    )

    if not files:
        print("No chapter-NNN.txt files found — already renamed or not yet proofread.")
        return

    print(f"Found {len(files)} chapters to process. dry_run={dry_run}\n")

    for filename in files:
        num = int(filename.replace("chapter-", "").replace(".txt", ""))
        in_path = os.path.join(proofread_dir, filename)

        with open(in_path, encoding="utf-8") as f:
            text = f.read()

        display_title, updated_text = enrich_title(num, text)
        safe_title = _sanitize(display_title)
        new_name = f"Chapter {num:03d} - {safe_title}.txt"
        new_path = os.path.join(proofread_dir, new_name)

        if display_title != text.splitlines()[0].strip():
            print(f"  [{num:03d}] GENERATED subtitle → {new_name}")
        else:
            print(f"  [{num:03d}] {new_name}")

        if not dry_run:
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(updated_text)
            os.rename(in_path, new_path)

            if voice_dir:
                mp3_old = os.path.join(voice_dir, filename.replace(".txt", ".mp3"))
                if os.path.exists(mp3_old):
                    mp3_new = os.path.join(voice_dir, new_name.replace(".txt", ".mp3"))
                    os.rename(mp3_old, mp3_new)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without renaming")
    parser.add_argument("--proofread-dir", default=PROOFREAD_DIR)
    parser.add_argument("--voice-dir", default=None, help="Also rename matching .mp3 files")
    args = parser.parse_args()
    run(dry_run=args.dry_run, proofread_dir=args.proofread_dir, voice_dir=args.voice_dir)
