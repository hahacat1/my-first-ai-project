#!/usr/bin/env python3
"""
Proofread webnovel chapters using a local Ollama model.

Usage:
    python3 proofreader/proofread.py                  # all chapters
    python3 proofreader/proofread.py --test            # chapter 1 only (test run)
    python3 proofreader/proofread.py --start 10        # resume from chapter 10

Reads from:  output/if-you-dont-become-the-main-character-youll-die/
Saves to:    output/proofread/
Progress is saved so you can stop and resume anytime.
"""

import argparse
import os
import time
import json
import ollama

INPUT_DIR = "output/if-you-dont-become-the-main-character-youll-die"
OUTPUT_DIR = "output/proofread"
MODEL = "qwen3.5:9b"

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


def proofread_chapter(text: str) -> str:
    prompt = PROMPT_TEMPLATE.format(text=text)
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.2},
    )
    return response["message"]["content"].strip()


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
