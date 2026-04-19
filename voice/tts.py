"""
Voice generation using Kokoro TTS (local, free).
Install: pip install kokoro soundfile

Reads proofread chapter .txt files → saves .mp3 per chapter into output/<novel>/voice/
"""

import os
import json
import soundfile as sf


def _load_kokoro():
    try:
        from kokoro import KPipeline
        return KPipeline(lang_code="a")  # 'a' = American English
    except ImportError:
        raise ImportError(
            "Kokoro TTS not installed. Run:\n"
            "  pip install kokoro soundfile\n"
            "  pip install kokoro[extra]  (for all voices)"
        )


def generate_chapter(text: str, out_path: str, pipeline=None, voice: str = "af_heart") -> None:
    """Convert a single chapter text to mp3."""
    import numpy as np

    if pipeline is None:
        pipeline = _load_kokoro()

    audio_chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=1.0):
        audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError(f"Kokoro produced no audio for: {out_path}")

    combined = np.concatenate(audio_chunks)
    sf.write(out_path, combined, 24000)


def generate_all(in_dir: str, out_dir: str, voice: str = "af_heart") -> None:
    """
    Generate mp3 for every proofread chapter that doesn't have one yet.
    Saves to out_dir/chapter-NNN.mp3
    """
    os.makedirs(out_dir, exist_ok=True)

    chapters = sorted([
        f for f in os.listdir(in_dir)
        if f.startswith("chapter-") and f.endswith(".txt")
    ])

    print(f"Voice: Kokoro TTS ({voice})")
    print(f"Chapters: {len(chapters)}")

    pipeline = _load_kokoro()

    progress_file = os.path.join(out_dir, ".progress.json")
    done = set(json.load(open(progress_file)) if os.path.exists(progress_file) else [])

    for i, filename in enumerate(chapters, 1):
        mp3_name = filename.replace(".txt", ".mp3")
        if mp3_name in done:
            print(f"  [{i}/{len(chapters)}] {mp3_name} already done, skipping")
            continue

        in_path = os.path.join(in_dir, filename)
        out_path = os.path.join(out_dir, mp3_name)

        with open(in_path, encoding="utf-8") as f:
            text = f.read()

        print(f"  [{i}/{len(chapters)}] {mp3_name}...", end=" ", flush=True)
        try:
            generate_chapter(text, out_path, pipeline=pipeline, voice=voice)
            size_kb = os.path.getsize(out_path) // 1024
            print(f"done ({size_kb} KB)")
            done.add(mp3_name)
            with open(progress_file, "w") as f:
                json.dump(list(done), f)
        except Exception as e:
            print(f"FAILED: {e}")
