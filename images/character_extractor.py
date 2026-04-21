"""
Uses LM Studio to scan proofread chapters and build detailed anime character profiles.
Acts as an anime character designer to extract precise visual descriptions for ComfyUI.
Scans ALL chapters to catch characters introduced later in the story.
"""

from __future__ import annotations
import os
import json
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

EXTRACT_SYSTEM = """You are a professional anime character designer creating reference sheets for a ComfyUI Stable Diffusion pipeline.

Read the chapter excerpt and extract EVERY named character who has at least one explicit physical detail (hair, eyes, build, clothing, face, expression).

RULES — violate any and the output becomes unusable:

RULE 1 — ONLY EXTRACT VISUALLY DESCRIBED CHARACTERS
Only characters with at least one explicit physical detail. Never invent or assume. If named but no physical description, skip entirely.

RULE 2 — EYE COLOR IS MANDATORY
Must include explicit or narratively appropriate eye color. If not stated: dark brown (East Asian-coded), grey or brown (European-coded), warm hazel (ambiguous).
Format exactly: "dark brown eyes", "grey eyes", "warm hazel eyes"
Never leave unspecified — SD defaults to glowing red or electric blue.

RULE 3 — CLOTHING MUST MATCH STATUS
Clothing must exactly reflect occupation, social status, and scene context. Infer only from text. Never default to noble/elegant unless explicitly stated.
- Poor / street character: worn simple clothes, patched fabric, rough linen
- Merchant: practical layered clothes, modest quality
- Noble: fine tailored fabric, subtle ornamentation — ONLY if text explicitly states nobility
- Guard / soldier: functional uniform, not decorative unless stated

RULE 4 — PURE BOORU TAGS ONLY
All tag fields must be comma-separated Danbooru-style tags. No sentences. No prose. No "he has".
Good: "dark brown messy hair, wide dark brown eyes, pale skin, worn linen shirt, slim build"
Bad: "He has messy dark hair and looks confused with wide eyes"

RULE 5 — CLOTHING NEGATIVE FIELD
Always include clothing_negative to block wrong outfits and SD style bleed.
Always add these base terms at the end: realistic, photorealistic, 3d render, photograph

RULE 6 — ROLE ASSIGNMENT
protagonist: main POV character or hero
antagonist: actively opposes protagonist with power or threat
supporting: recurring named character with story importance
minor: appears once or briefly

RULE 7 — FACTUAL DESCRIPTION ONLY
"description" = single clean paragraph, facts only. No "appears to", "seems", "looks like", "might be".
Wrong: "He appears to be a young man who seems confused"
Right: "Young adult male, slim build, pale skin, dark brown messy hair falling across his forehead, wide dark brown eyes, perpetually dazed expression"

RULE 8 — AGE AS FEEL, NOT EXACT
Use only: child, young teenager, teenager, young adult, mid-twenties, late twenties, mid-thirties, middle-aged, elderly.

RULE 9 — master_tags IS THE SINGLE SOURCE OF TRUTH
master_tags is the one clean repeatable booru string used in every future ComfyUI generation.
Must include: hair + eye color + skin tone + build + clothing summary + expression.
This is what gets pasted into ComfyUI every single time. Make it complete and exact.
A valid master_tags has at least 6 comma-separated tags.

RULE 10 — character_trigger MUST BE UNIQUE AND SAFE
character_trigger is a 1-3 word snake_case identifier for future LoRA training.
Format: firstname_trait or nickname_role. Examples: "dazed_leo", "cold_innkeeper", "scarred_captain"
Never use a single common English word alone (bad: "hero", "boy", "man").
Never use punctuation other than underscores.
Must be lowercase only.

RULE 11 — UNNAMED RECURRING CHARACTERS
If a character is referred to only by title ("the innkeeper", "the blacksmith") but appears with physical details, assign a temporary name in format "Innkeeper_001" for this extraction only. The refinement step will merge them later.

Output ONLY a valid JSON array. No explanation, no code fences, no extra text before or after the array.
[
  {
    "name": "Exact Character Name",
    "role": "protagonist/antagonist/supporting/minor",
    "character_trigger": "unique_trigger",
    "description": "single factual paragraph",
    "eye_color": "dark brown eyes",
    "clothing": "worn linen shirt, patched trousers, simple leather belt",
    "clothing_negative": "noble robes, armor, gold trim, military uniform, crown, realistic, photorealistic, 3d render, photograph",
    "default_expression": "perpetually dazed, slightly confused",
    "tags": "slim build, pale skin, dark brown messy hair, wide dark brown eyes, worn linen shirt",
    "master_tags": "slim build, pale skin, dark brown messy hair falling across forehead, wide dark brown eyes, perpetually dazed expression, worn linen shirt, patched trousers, simple leather belt"
  }
]"""

EXTRACT_USER = """Extract all visually described characters from this chapter text.

TEXT:
{text}"""

REFINE_SYSTEM = """You are merging multiple scene-by-scene descriptions of the SAME character into one definitive ComfyUI reference sheet.

RULES:

RULE 1 — FIRST APPEARANCE HAS PRIORITY
The first description is the most canonical. Use it as the base. Later descriptions only add detail or resolve gaps — they do not override unless more explicit.

RULE 2 — RESOLVE CONFLICTS: explicit > most frequent > most detailed
If one chapter says "brown eyes" and another doesn't mention eyes, use "brown eyes".
If clothing varies, use the outfit worn most often across all descriptions. Do not use rare or dramatic outfits as the default.

RULE 3 — NEVER INVENT
Only merge what is in the provided descriptions. Do not add details absent from all sources.

RULE 4 — EYE COLOR MUST ALWAYS BE PRESENT
If any source mentions eye color, it must appear in the final output.

RULE 5 — CLOTHING = DEFAULT APPEARANCE
The outfit worn most often across all descriptions, not the most dramatic or formal one.

RULE 6 — CLOTHING NEGATIVE MUST BE COMPREHENSIVE
Combine ALL clothing_negative tags from every description. Remove duplicates. Always include at the end: realistic, photorealistic, 3d render, photograph.

RULE 7 — master_tags IS THE PRIORITY OUTPUT
master_tags is the single clean repeatable booru string for every future ComfyUI generation.
Must be complete: hair + eyes + skin + build + clothing + expression. At least 6 comma-separated tags. Make it the best possible.

Output ONLY a single valid JSON object. No explanation, no code fences, no extra text.
{
  "name": "...",
  "role": "...",
  "character_trigger": "...",
  "description": "...",
  "eye_color": "...",
  "clothing": "...",
  "clothing_negative": "...",
  "default_expression": "...",
  "tags": "...",
  "master_tags": "..."
}"""

REFINE_USER = """Merge these descriptions of {name} into one definitive profile.

Descriptions:
{descriptions}"""

DEDUP_SYSTEM = """You are given a list of character names extracted from a webnovel, with mention counts.
Many entries refer to the same character under different names, titles, or partial names.

Return a JSON object mapping each CANONICAL name to a list of ALIASES that should be merged into it.
Only include groups with 2+ members. Omit singletons.

HARD RULES — violate any and the merge is wrong:

1. POSSESSIVE = DIFFERENT PERSON. If the alias contains an apostrophe-s possessive referencing the canonical name, they are DIFFERENT people. Never merge them.
   BAD: "Count Bermont's Henchman #1" → "Count Bermont"  (henchman ≠ the count)
   BAD: "Viscount's subordinate" → "Viscount"

2. NAMES MUST SHARE A ROOT WORD. Canonical and alias must share at least one name/word, OR the alias must be an obvious title variant of the canonical.
   GOOD: "Archbishop Butier" → "Butier"  (shares "Butier")
   GOOD: "Ferdinand Ertinez" → "Ferdinand"  (shares "Ferdinand")
   BAD: "Evil Dragon Vernis" → "Leonardo"  (no shared word; different entity type)
   BAD: "Lord Roald" → "Orlie"  (no shared word)

3. ENTITY TYPE MUST MATCH. A dragon, monster, or creature cannot be the same character as a human.

4. WHEN UNCERTAIN, DO NOT MERGE. Only merge when you are confident. A wrong merge destroys a character profile permanently.

5. CANONICAL = HIGHEST MENTION COUNT. If tied, use the most complete formal name.

6. PARENTHETICAL VARIANTS ARE SAFE. "(protagonist)", "(disguised)", "(young)", "(original)" suffixes on the same base name are safe to merge.
   GOOD: "Isaac (protagonist)" → "Isaac"
   GOOD: "Leonardo (young)" → "Leonardo"

7. "protagonist" / "I" / "narrator" variants: merge into the named character with most mentions.

Output ONLY a valid JSON object. No explanation, no code fences.
{"CanonicalName": ["Alias1", "Alias2"], ...}"""


def _dedup_profiles(all_profiles: dict) -> dict:
    """Merge case-duplicate and semantically-duplicate character names before refinement."""

    # Step 1: Case/spacing normalization (deterministic)
    normalized: dict[str, list[str]] = {}
    for name in list(all_profiles.keys()):
        key = name.lower().strip()
        normalized.setdefault(key, []).append(name)

    for variants in normalized.values():
        if len(variants) > 1:
            canonical = max(variants, key=lambda n: len(all_profiles[n]))
            for alias in variants:
                if alias != canonical and alias in all_profiles:
                    all_profiles[canonical].extend(all_profiles.pop(alias))
                    print(f"    Case merge: '{alias}' → '{canonical}'")

    # Step 2: Semantic dedup via LLM
    name_counts = sorted(
        ((name, len(profiles)) for name, profiles in all_profiles.items()),
        key=lambda x: -x[1],
    )
    names_text = "\n".join(f"{name} ({count} mentions)" for name, count in name_counts)

    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[
                {"role": "system", "content": DEDUP_SYSTEM},
                {"role": "user", "content": f"Character names:\n{names_text}"},
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        raw = resp.choices[0].message.content.strip()
        if "<think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        if "```" in raw:
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return all_profiles
        merges: dict = json.loads(raw[start:end])
        for canonical, aliases in merges.items():
            if canonical not in all_profiles:
                continue
            canonical_words = set(canonical.lower().split())
            for alias in aliases:
                if alias not in all_profiles or alias == canonical:
                    continue
                # Safety: never merge possessives (alias contains canonical + 's)
                if f"{canonical.lower()}'s" in alias.lower():
                    print(f"    Skipped possessive: '{alias}' → '{canonical}'")
                    continue
                # Safety: require at least one shared word between names
                alias_words = set(alias.lower().split())
                shared = canonical_words & alias_words - {"the", "a", "an", "of", "and"}
                if not shared:
                    print(f"    Skipped (no shared root): '{alias}' → '{canonical}'")
                    continue
                all_profiles[canonical].extend(all_profiles.pop(alias))
                print(f"    Semantic merge: '{alias}' → '{canonical}'")
    except Exception as e:
        print(f"    Semantic dedup LLM call failed ({e}), skipping")

    return all_profiles


def _extract_from_chunk(text: str) -> list[dict]:
    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": EXTRACT_USER.format(text=text)},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        if "<think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        if "```" in raw:
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        return json.loads(raw[start:end])
    except Exception:
        return []


def _validate_character(char: dict) -> dict:
    """Ensure required fields exist and master_tags meets minimum quality bar."""
    if not char.get("master_tags") or len(char["master_tags"].split(",")) < 6:
        # Assemble from parts if master_tags is missing or too short
        parts = [
            char.get("tags", ""),
            char.get("eye_color", ""),
            char.get("clothing", ""),
        ]
        char["master_tags"] = ", ".join(p for p in parts if p)
    if not char.get("eye_color"):
        char["eye_color"] = "dark brown eyes"
    if not char.get("character_trigger"):
        slug = char.get("name", "character").lower().replace(" ", "_")[:20]
        char["character_trigger"] = f"{slug}_char"
    return char


def _refine_character(name: str, raw_profiles: list[dict]) -> dict | None:
    if len(raw_profiles) == 1:
        return _validate_character(raw_profiles[0])
    descriptions = "\n---\n".join([
        json.dumps(p, ensure_ascii=False, indent=2) for p in raw_profiles
    ])
    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[
                {"role": "system", "content": REFINE_SYSTEM},
                {"role": "user", "content": REFINE_USER.format(
                    name=name, descriptions=descriptions
                )},
            ],
            temperature=0.1,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()
        if "<think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        if "```" in raw:
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        result = json.loads(raw[start:end])
        return _validate_character(result)
    except Exception:
        return None


def extract_characters(proofread_dir: str, seed_characters: list = None,
                       batch_size: int = 30) -> list:
    """
    Scan proofread chapters and extract detailed anime character profiles.
    Saves progress after each chapter — safe to resume if interrupted.
    """
    chapters = sorted([
        f for f in os.listdir(proofread_dir)
        if (f.startswith("chapter-") or f.startswith("Chapter ")) and f.endswith(".txt")
    ])

    novel_dir = os.path.dirname(proofread_dir)
    progress_file = os.path.join(novel_dir, "characters_progress.json")

    if os.path.exists(progress_file):
        with open(progress_file) as f:
            saved = json.load(f)
        all_profiles: dict[str, list[dict]] = saved.get("profiles", {})
        scanned = saved.get("scanned", 0)
        print(f"  Resuming from chapter {scanned + 1} ({len(all_profiles)} characters found so far)")
    else:
        all_profiles = {}
        scanned = 0

    chunk_size = 4000
    total = len(chapters)

    # Process all remaining chapters in batches, saving progress after each batch
    while scanned < total:
        batch_end = min(scanned + batch_size, total)
        to_scan = chapters[scanned:batch_end]
        print(f"  Scanning chapters {scanned + 1}–{batch_end} of {total}...")

        for i, ch in enumerate(to_scan, 1):
            with open(os.path.join(proofread_dir, ch), encoding="utf-8") as f:
                text = f.read()

            words = text.split()
            for start in range(0, len(words), chunk_size):
                chunk = " ".join(words[start:start + chunk_size])
                chars = _extract_from_chunk(chunk)
                for c in chars:
                    name = c.get("name", "").strip()
                    if not name:
                        continue
                    all_profiles.setdefault(name, [])
                    all_profiles[name].append(c)

            print(f"    [{scanned + i}/{total}] {ch[:50]} — {len(all_profiles)} characters total")

            with open(progress_file, "w") as f:
                json.dump({"profiles": all_profiles, "scanned": scanned + i}, f)

        scanned = batch_end

    print(f"  Scan complete. Deduplicating {len(all_profiles)} character names...")
    all_profiles = _dedup_profiles(all_profiles)
    print(f"  After dedup: {len(all_profiles)} unique characters. Refining...")

    final_characters = []
    for name, profiles in all_profiles.items():
        refined = _refine_character(name, profiles)
        if refined:
            final_characters.append(refined)
            print(f"    Refined: {name} ({len(profiles)} sources)")
        else:
            final_characters.append(_validate_character(profiles[0]))

    if seed_characters:
        seed_names = {c["name"] for c in seed_characters}
        final_characters = [c for c in final_characters if c["name"] not in seed_names]
        final_characters = seed_characters + final_characters

    out_path = os.path.join(novel_dir, "characters.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_characters, f, indent=2, ensure_ascii=False)

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
                f.write(f"# Role: {char.get('role', 'supporting')}\n")
                f.write(f"# Trigger: {char.get('character_trigger', '')}\n\n")
                f.write(f"[DESCRIPTION]\n{char.get('description', '')}\n\n")
                f.write(f"[EYE COLOR]\n{char.get('eye_color', '')}\n\n")
                f.write(f"[CLOTHING]\n{char.get('clothing', '')}\n\n")
                f.write(f"[DEFAULT EXPRESSION]\n{char.get('default_expression', '')}\n\n")
                f.write(f"[MASTER TAGS]\n{char.get('master_tags', '')}\n\n")
                f.write(f"[POSITIVE PROMPT]\n{positive}\n\n")
                f.write(f"[NEGATIVE PROMPT]\n{negative}\n")

    print(f"  Characters saved: {out_path} ({len(final_characters)} total)")
    print(f"  Prompts written to: {chars_root}/<character_name>/prompt.txt")

    return final_characters
