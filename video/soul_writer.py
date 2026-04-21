"""
Generates a soul.md production bible for a novel from its first 10 chapters + characters.json.
Run once per novel. If soul.md already exists, skips — hand edits are preserved.

Usage (via pipeline):
    python pipeline/run.py --novel <slug> --stages soul
"""

from __future__ import annotations
import os
import json
from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

_client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

SOUL_SYSTEM_TEMPLATE = """You are a visual production designer writing a permanent reference document for an anime video series adapted from a Korean web novel.

Your output is soul.md — a production bible that every future AI video director and API call will receive as context. It must be written for a machine that has never read the novel, not for a human reader.

Read the provided chapter excerpts and character data, then write the soul.md following these rules exactly.

---

RULE 1 — PURPOSE AND AUDIENCE
This document is machine context, not a summary. Write for an AI that will generate video frames.
Every line must answer: "What should the AI render?" — not "What happens in the story?"
Avoid plot summaries, character arcs, themes, or literary analysis. Those belong in a synopsis, not a soul.

---

RULE 2 — CANONICAL CAST (required section)
Write one block per major character. Include only characters who appear in 3+ chapters across the sample.
Each block must contain:
- Full name as it appears most consistently
- Physical description: hair (color, length, texture), eyes (color, shape), build, height feel, skin tone
- Age feel (do not guess exact age — "early 20s", "mid-30s", "elderly")
- Signature expression or default emotional register
- One item of recurring costume or prop (if established)
- Pronoun (he/him, she/her, they/them)
- 2-3 sentences maximum per character

Do NOT include characters who appear only once, named extras, or unnamed crowd figures.
Do NOT write personality traits, backstory, or motivations — visual only.

---

RULE 3 — ART STYLE (required section)
Write the exact style tag string to prefix every shot prompt. 8-12 words max.
Derive from: the novel's target audience, the art style config, and the visual tone of the chapters.
Format: comma-separated tags, no parentheses.
Example: masterpiece, best quality, Korean manhwa, BL romance, rich jewel tones, delicate lineart

Then write 3-5 additional notes on visual conventions specific to this story:
- Line weight tendencies (delicate vs bold)
- Color saturation (muted vs jewel-toned vs washed out)
- Whether faces are expressive/detailed or simplified
- Background detail level (sparse vs rich)
- Panel energy (calm and composed vs kinetic and loose)

---

RULE 4 — WORLD AESTHETIC (required section)
Describe the physical world in visual terms only. What does this world look like on screen?
Cover:
- Time period and setting feel (medieval European, contemporary Korean, fantasy city, etc.)
- Architecture: stone vs wood vs glass, scale, state of repair
- Interior environments: inn, castle hall, alley, harbor — what are their defining visual qualities
- Exterior environments: what time of day is most common, what weather and light quality
- Objects and props that recur (documents, weapons, food, clothing details)

4-6 sentences. No worldbuilding lore. No magic systems. Visual only.

---

RULE 5 — LIGHTING PALETTE (required section)
List 4-6 named lighting setups that are native to this story. For each:
- Name (2-4 words)
- When it appears (scene type or emotional context)
- What it looks like (color temperature, direction, shadow quality)

Example:
- Candlelit Interior: indoor night scenes, scheming or intimate conversation — warm amber, deep uneven shadows, faces half-lit
- Overcast Exterior: outdoor daytime, neutral or melancholy moments — cool diffused fill, soft shadows, low contrast
- Cold Blue Shadow: danger, grief, isolation — cold directional fill, high contrast, shadows towards camera

Do not invent lighting that doesn't match the chapters provided.

---

RULE 6 — TONE AND EMOTIONAL REGISTER (required section)
3-4 sentences describing what this story feels like visually.
Focus on: pacing (slow and contemplative vs fast and kinetic), emotional temperature (warm vs cold), tension style (slow dread vs sudden shock), and the dominant mood across most episodes.
This is not a genre label. Describe the actual visual rhythm of the chapters.

---

RULE 7 — WHAT TO AVOID (required section)
List 5-8 specific visual mistakes that would break the aesthetic of this story.
These must be concrete and actionable, not generic advice.
Wrong: "don't use bad lighting" — too vague
Right: "no high-saturation neon colors — this palette is jewel-toned but never electric"
Right: "no modern urban architecture — all interiors are pre-industrial stone or timber"
Right: "no beach or tropical settings — all exteriors are urban, harbor, or enclosed courtyard"

---

RULE 8 — OUTPUT FORMAT
Write clean markdown. Use these exact section headers:
## Canonical Cast
## Art Style
## World Aesthetic
## Lighting Palette
## Tone and Emotional Register
## What to Avoid

No introduction paragraph. No conclusion. No commentary outside the sections.
Start the file with: # Soul — [Novel Title]
"""


def _read_sample_chapters(proofread_dir: str, n: int = 5, chars_per: int = 1500) -> str:
    """Read first n proofread chapters, capped per chapter to stay within LLM context."""
    files = sorted([
        f for f in os.listdir(proofread_dir)
        if f.endswith(".txt")
    ])[:n]
    parts = []
    for f in files:
        path = os.path.join(proofread_dir, f)
        with open(path, encoding="utf-8") as fh:
            text = fh.read(chars_per)
        parts.append(f"=== {f} ===\n{text}")
    return "\n\n".join(parts)


def _read_characters(novel_dir: str) -> str:
    chars_path = os.path.join(novel_dir, "characters.json")
    if not os.path.exists(chars_path):
        return ""
    with open(chars_path, encoding="utf-8") as fh:
        data = json.load(fh)
    # Only pass canonical characters (have pronoun field)
    canonical = [c for c in data if "pronoun" in c]
    return json.dumps(canonical, indent=2, ensure_ascii=False)


def write_soul(novel: dict, novel_dir: str) -> str:
    """
    Generate soul.md for the novel. Skips if already exists.
    Returns path to soul.md.
    """
    output_path = os.path.join(novel_dir, "video", "soul.md")
    if os.path.exists(output_path):
        print(f"  soul.md already exists — skipping (delete to regenerate)")
        return output_path

    slug = novel["slug"]
    title = novel.get("title", slug)
    art_style = novel.get("art_style", "")
    audience = novel.get("audience", "")

    proofread_dir = os.path.join(novel_dir, "proofread")
    if not os.path.isdir(proofread_dir):
        print(f"  No proofread chapters found at {proofread_dir} — skipping soul stage")
        return output_path

    print(f"  Reading sample chapters...")
    chapter_sample = _read_sample_chapters(proofread_dir, n=5, chars_per=1500)
    characters_json = _read_characters(novel_dir)

    user_message = f"""Novel title: {title}
Target audience: {audience}
Art style config: {art_style}

CANONICAL CHARACTERS (from characters.json):
{characters_json if characters_json else "(none defined yet)"}

CHAPTER SAMPLE (first 10 chapters):
{chapter_sample}

Write soul.md now."""

    print(f"  Generating soul.md via LM Studio...")
    response = _client.chat.completions.create(
        model=LM_STUDIO_MODEL,
        messages=[
            {"role": "system", "content": SOUL_SYSTEM_TEMPLATE},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip <think> blocks from reasoning models
    if "<think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(raw)

    print(f"  soul.md written to {output_path}")
    return output_path
