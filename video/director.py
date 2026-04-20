"""
Uses LM Studio to write storyboard-style director prompts for each chapter.
Each shot prompt = ~10-15 seconds of video. Target ~12-18 shots per chapter (~3 min).
The model decides how many beats and shots the chapter naturally needs.
Output: director_prompts/chapter-NNN.json (review/edit before video generation).
"""

from __future__ import annotations
import os
import json
import re
from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

_client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

DIRECTOR_SYSTEM = """You are an anime film director adapting a Korean web novel chapter into a visual storyboard.

Read the chapter and:
1. Write a 3-4 sentence SYNOPSIS summarising the episode's story arc and emotional tone.
2. Break the chapter into dramatic beats naturally — as many as the content needs. Each beat is a scene shift, emotional change, dialogue moment, or action sequence.
3. For each beat, write as many shot prompts as that moment deserves. Each shot will become ~10-15 seconds of video. Aim for a total of 12-18 shots across the whole episode (roughly 3 minutes of finished video), but let the story guide you — a quiet chapter may need fewer shots, an action chapter more.

Shot variety per beat (mix freely, don't force all four every time):
- Wide establishing: set the scene and location
- Medium action: character doing something
- Close-up emotion: face, hands, reaction
- Cutaway detail: object, environment, symbol that adds meaning

Each shot prompt must be:
- 20-35 words maximum
- ONE camera move: slow push-in / tracking shot / Dutch tilt / dolly zoom / aerial pan / over-the-shoulder
- ONE subject action
- Character name included if known
- End with: "anime cel-shaded, 4K"
- Lighting: golden hour / moonlit / dramatic chiaroscuro / soft diffused / neon-lit

Output ONLY valid JSON, no other text:
{
  "synopsis": "3-4 sentence summary of the episode here.",
  "beats": [
    {
      "beat": "one sentence describing what happens",
      "shots": [
        "shot prompt here, anime cel-shaded, 4K",
        "shot prompt here, anime cel-shaded, 4K"
      ]
    }
  ]
}"""


def _parse_response(raw: str) -> tuple[str, list[dict]]:
    """
    Extract synopsis + beats from model output.
    Returns (synopsis_str, beats_list). Falls back to ("", []) on failure.
    """
    if "<think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    # Try new {synopsis, beats} object format first
    obj_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            if isinstance(data, dict) and "beats" in data:
                synopsis = data.get("synopsis", "")
                beats = _validate_beats(data["beats"])
                if beats:
                    return synopsis, beats
        except json.JSONDecodeError:
            pass

    # Fall back to bare array format (old prompt style)
    arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if arr_match:
        try:
            beats = _validate_beats(json.loads(arr_match.group(0)))
            if beats:
                return "", beats
        except json.JSONDecodeError:
            pass

    return "", []


def _validate_beats(raw_beats) -> list[dict]:
    valid = []
    for b in raw_beats:
        if isinstance(b, dict) and "beat" in b and "shots" in b:
            shots = b["shots"]
            if isinstance(shots, list) and len(shots) >= 2:
                valid.append({"beat": b["beat"], "shots": shots[:4]})
    return valid


def _fallback_entry() -> tuple[str, list[dict]]:
    return "", [{"beat": "scene", "shots": [
        "Wide establishing shot, soft diffused light, anime cel-shaded, 4K",
        "Medium shot, character in focus, tracking shot, anime cel-shaded, 4K",
        "Close-up on face, emotional expression, slow push-in, anime cel-shaded, 4K",
        "Cutaway detail, over-the-shoulder, moonlit, anime cel-shaded, 4K",
    ]}]


def write_director_prompts(chapters: list[dict], prompts_dir: str,
                           primary_characters: dict | None = None) -> list[dict]:
    """
    For each chapter, generate beat-level storyboard prompts via Ollama.
    chapters: list of {filename, text} dicts (from segmenter)
    primary_characters: optional {filename: character_name} for character-aware prompts
    Returns chapters with added 'beats' field.
    """
    os.makedirs(prompts_dir, exist_ok=True)
    primary_characters = primary_characters or {}

    results = []
    print(f"  Writing storyboard prompts for {len(chapters)} chapters...")

    for i, ch in enumerate(chapters, 1):
        filename = ch["filename"]
        cache_path = os.path.join(prompts_dir, filename.replace(".txt", ".json"))

        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            ch["beats"] = cached["beats"]
            ch["synopsis"] = cached.get("synopsis", "")
            print(f"  [{i}/{len(chapters)}] {filename} (cached, {len(ch['beats'])} beats)")
            results.append(ch)
            continue

        char_name = primary_characters.get(filename, "")
        char_hint = f"\nPrimary character in this chapter: {char_name}" if char_name else ""

        print(f"  [{i}/{len(chapters)}] {filename}...", end=" ", flush=True)
        try:
            resp = _client.chat.completions.create(
                model=LM_STUDIO_MODEL,
                messages=[
                    {"role": "system", "content": DIRECTOR_SYSTEM},
                    {"role": "user", "content": f"{char_hint}\n\nCHAPTER TEXT:\n{ch['text'][:3000]}"}
                ],
                temperature=0.7,
                max_tokens=10000,
            )
            raw = resp.choices[0].message.content.strip()
            synopsis, beats = _parse_response(raw)
            if beats:
                print(f"done ({len(beats)} beats)")
            else:
                synopsis, beats = _fallback_entry()
                print("fallback (parse failed)")
        except Exception as e:
            synopsis, beats = _fallback_entry()
            print(f"fallback ({e})")

        ch["beats"] = beats
        ch["synopsis"] = synopsis
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"filename": filename, "synopsis": synopsis, "beats": beats},
                      f, indent=2, ensure_ascii=False)
        results.append(ch)

    print(f"  Storyboard prompts saved to: {prompts_dir}")
    print(f"  TIP: Edit .json files in {prompts_dir} to refine prompts before generating video.")
    return results
