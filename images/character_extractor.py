"""
Uses LM Studio to scan proofread chapters and build detailed anime character profiles.
Acts as an anime art director to extract rich visual descriptions for ComfyUI generation.
Scans ALL chapters to catch characters introduced later in the story.
"""

from __future__ import annotations
import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

EXTRACT_PROMPT = """You are an expert anime art director and character designer with 20 years of experience.

Read this excerpt from a Korean web novel and extract every named character with a physical description.

For each character, provide an ANIME-STYLE visual description that could be used to generate a character portrait in Stable Diffusion. Be specific and detailed about:
- Age appearance (teenager, young adult, middle-aged, elderly)
- Hair: color, length, style (e.g. "long silver hair with loose waves", "short messy black hair")
- Eyes: color and shape (e.g. "sharp crimson eyes", "gentle blue eyes with long lashes")
- Build: height and body type (e.g. "tall slender build", "petite feminine figure", "muscular broad-shouldered")
- Skin tone (e.g. "pale porcelain skin", "warm tan complexion")
- Clothing/outfit style (e.g. "elegant dark noble robes with gold trim", "worn leather adventurer gear")
- Notable features (scars, accessories, aura, expression tendency)
- Personality hint visible in appearance (e.g. "cold sharp gaze", "warm gentle smile")

Format as JSON array:
[
  {{
    "name": "Character Name",
    "role": "protagonist/antagonist/supporting/minor",
    "description": "detailed anime visual description as one paragraph",
    "tags": "comma-separated SD tags: hair color, eye color, clothing style, body type, expression"
  }}
]

Only include characters with enough physical description to draw them. Return ONLY the JSON array.

TEXT:
{text}"""

REFINE_PROMPT = """You are an expert anime art director. You have collected descriptions of the same character from multiple chapters of a novel.

Merge these descriptions into ONE definitive character profile. Keep the most specific and consistent details. Resolve any contradictions by preferring the most detailed description.

Character: {name}
Descriptions collected:
{descriptions}

Return a single JSON object:
{{
  "name": "{name}",
  "role": "protagonist/antagonist/supporting/minor",
  "description": "definitive detailed anime visual description as one paragraph",
  "tags": "comma-separated SD tags: hair color, eye color, clothing style, body type, expression"
}}

Return ONLY the JSON object."""


def _extract_from_chunk(text: str) -> list[dict]:
    """Extract characters from a text chunk via LM Studio."""
    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=text)}],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        # Find JSON array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        return json.loads(raw[start:end])
    except Exception as e:
        return []


def _refine_character(name: str, descriptions: list[str]) -> dict | None:
    """Ask LM Studio to merge multiple descriptions into one definitive profile."""
    if len(descriptions) == 1:
        return None  # No need to merge
    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[{"role": "user", "content": REFINE_PROMPT.format(
                name=name,
                descriptions="\n---\n".join(descriptions)
            )}],
            temperature=0.1,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(raw[start:end])
    except Exception:
        return None


def extract_characters(proofread_dir: str, seed_characters: list = None,
                        batch_size: int = 30) -> list:
    """
    Scan proofread chapters in batches and extract detailed anime character profiles.
    Saves progress after each batch — safe to resume if LM Studio stalls.
    Default: first 30 chapters (covers the full main cast for most novels).
    """
    chapters = sorted([
        f for f in os.listdir(proofread_dir)
        if (f.startswith("chapter-") or f.startswith("Chapter ")) and f.endswith(".txt")
    ])

    novel_dir = os.path.dirname(proofread_dir)
    progress_file = os.path.join(novel_dir, "characters_progress.json")

    # Resume from saved progress if it exists
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            saved = json.load(f)
        all_mentions: dict[str, list[str]] = saved.get("mentions", {})
        scanned = saved.get("scanned", 0)
        print(f"  Resuming from chapter {scanned + 1} ({len(all_mentions)} characters found so far)")
    else:
        all_mentions = {}
        scanned = 0

    to_scan = chapters[scanned:scanned + batch_size]
    print(f"  Scanning chapters {scanned + 1}–{scanned + len(to_scan)} of {len(chapters)} (batch of {batch_size})...")

    chunk_size = 4000  # words per LM Studio call

    for i, ch in enumerate(to_scan, 1):
        with open(os.path.join(proofread_dir, ch), encoding="utf-8") as f:
            text = f.read()

        words = text.split()
        for start in range(0, len(words), chunk_size):
            chunk = " ".join(words[start:start + chunk_size])
            chars = _extract_from_chunk(chunk)
            for c in chars:
                name = c.get("name", "").strip()
                desc = c.get("description", "").strip()
                if name and desc:
                    all_mentions.setdefault(name, [])
                    if desc not in all_mentions[name]:
                        all_mentions[name].append(desc)

        print(f"    [{i}/{len(to_scan)}] {ch[:50]} — {len(all_mentions)} characters total")

        # Save progress after every chapter
        with open(progress_file, "w") as f:
            json.dump({"mentions": all_mentions, "scanned": scanned + i}, f)

    print(f"  Scan complete. Found {len(all_mentions)} unique characters. Refining profiles...")

    # Merge multiple descriptions per character into one definitive profile
    final_characters = []
    for name, descs in all_mentions.items():
        if len(descs) > 1:
            refined = _refine_character(name, descs)
            if refined:
                final_characters.append(refined)
                print(f"    Refined: {name} ({len(descs)} sources)")
                continue
        # Single description or failed merge — use first/best description
        final_characters.append({
            "name": name,
            "description": descs[0],
            "tags": "",
            "role": "supporting",
        })

    # Merge seed characters from config (they take priority)
    if seed_characters:
        seed_names = {c["name"] for c in seed_characters}
        final_characters = [c for c in final_characters if c["name"] not in seed_names]
        final_characters = seed_characters + final_characters

    # Save master characters.json
    novel_dir = os.path.dirname(proofread_dir)
    out_path = os.path.join(novel_dir, "characters.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_characters, f, indent=2, ensure_ascii=False)

    # Save each character's prompt.txt in their own folder for review/editing
    from images.prompts import character_portrait_prompt
    chars_root = os.path.join(novel_dir, "characters")
    for char in final_characters:
        name_slug = char["name"].lower().replace(" ", "_").replace("/", "_")
        char_dir = os.path.join(chars_root, name_slug)
        os.makedirs(char_dir, exist_ok=True)
        prompt_path = os.path.join(char_dir, "prompt.txt")
        if not os.path.exists(prompt_path):
            positive, negative = character_portrait_prompt(char)
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(f"# Character: {char['name']}\n")
                f.write(f"# Role: {char.get('role', 'supporting')}\n\n")
                f.write(f"[DESCRIPTION]\n{char.get('description', '')}\n\n")
                f.write(f"[POSITIVE PROMPT]\n{positive}\n\n")
                f.write(f"[NEGATIVE PROMPT]\n{negative}\n")

    print(f"  Characters saved: {out_path} ({len(final_characters)} total)")
    print(f"  Prompts written to: {chars_root}/<character_name>/prompt.txt")
    print(f"  Review and edit prompts before running image generation.")

    return final_characters
