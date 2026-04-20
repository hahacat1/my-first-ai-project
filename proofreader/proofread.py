#!/usr/bin/env python3
"""
Proofread webnovel chapters using a local Ollama model.

Usage:
    python3 proofreader/proofread.py                  # all chapters
    python3 proofreader/proofread.py --test            # chapter 1 only (test run)
    python3 proofreader/proofread.py --start 10        # resume from chapter 10

Reads from:  novels/if-you-dont-become-the-main-character-youll-die/chapters/
Saves to:    novels/if-you-dont-become-the-main-character-youll-die/proofread/
Progress is saved so you can stop and resume anytime.
"""

import argparse
import os
import time
import json
from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

INPUT_DIR = "novels/if-you-dont-become-the-main-character-youll-die/chapters"
OUTPUT_DIR = "novels/if-you-dont-become-the-main-character-youll-die/proofread"
MODEL = LM_STUDIO_MODEL

PROMPT_TEMPLATE = """You are a proofreader for a Korean-to-English translated web novel called "If You Don't Become the Main Character, You'll Die".

Your job:
- Fix awkward phrasing and unnatural English that came from literal Korean translation
- Fix grammar and punctuation errors
- Improve sentence flow so it reads naturally
- Keep ALL story content, character names, plot details, and the author's style intact
- Do NOT add or remove any story events or dialogue
- Do NOT add commentary or explanations

Return ONLY the corrected chapter text. Nothing else.

--- CHAPTER TO PROOFREAD ---
{text}
--- END ---"""


def _proofread_chunk(chunk: str) -> str:
    """Send a single small chunk to the model and return corrected text."""
    prompt = PROMPT_TEMPLATE.format(text=chunk)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def proofread_chapter(text: str, chunk_words: int = 200) -> str:
    """Split chapter into small chunks, proofread each, then rejoin."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = []
    current_words = 0

    for para in paragraphs:
        words = len(para.split())
        if current_words + words > chunk_words and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_words = words
        else:
            current.append(para)
            current_words += words

    if current:
        chunks.append("\n\n".join(current))

    corrected_chunks = [_proofread_chunk(c) for c in chunks]
    return "\n\n".join(corrected_chunks)


def get_chapter_files() -> list[str]:
    files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.startswith("chapter-") and f.endswith(".txt")
    ])
    return files


def load_progress() -> set:
    progress_file = os.path.join(OUTPUT_DIR, ".progress.json")
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            return set(json.load(f))
    return set()


def save_progress(done: set):
    progress_file = os.path.join(OUTPUT_DIR, ".progress.json")
    with open(progress_file, "w") as f:
        json.dump(list(done), f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run on chapter 1 only")
    parser.add_argument("--start", type=int, default=1, help="Start from chapter N")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    chapters = get_chapter_files()
    if args.test:
        chapters = chapters[:1]
    elif args.start > 1:
        chapters = chapters[args.start - 1:]

    done = load_progress()
    remaining = [c for c in chapters if c not in done]

    print(f"Model:     {MODEL}")
    print(f"Chapters:  {len(remaining)} to process")
    print(f"Output:    {OUTPUT_DIR}")
    print("-" * 50)

    times = []
    for i, filename in enumerate(remaining, start=1):
        in_path = os.path.join(INPUT_DIR, filename)
        out_path = os.path.join(OUTPUT_DIR, filename)

        with open(in_path, encoding="utf-8") as f:
            original = f.read()

        print(f"[{i}/{len(remaining)}] {filename} ({len(original)} chars)...", end=" ", flush=True)
        t0 = time.time()

        try:
            corrected = proofread_chapter(original)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(corrected)

            elapsed = time.time() - t0
            times.append(elapsed)
            avg = sum(times) / len(times)
            eta_mins = (len(remaining) - i) * avg / 60

            print(f"done ({elapsed:.0f}s) — ETA: {eta_mins:.0f} min remaining")
            done.add(filename)
            save_progress(done)

        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nFinished! {len(done)} chapters saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
