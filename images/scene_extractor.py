"""
Uses LM Studio to extract scene descriptions from chapters for ComfyUI background generation.
Scene images serve as environment references for DomoAI Character-to-Video.

Each chapter gets 1-3 scenes based on major location changes.
Recurring locations are merged across chapters for a definitive reference.
Characters present are linked via master_tags for composite generation.
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

SCENE_EXTRACT_SYSTEM = """You are a professional anime background artist and art director creating environment reference sheets for a ComfyUI Stable Diffusion + DomoAI Character-to-Video pipeline.

Read the chapter excerpt and extract ALL major scenes (1–3 maximum). Prioritize the most narratively important environments.

RULES — violate any and the output becomes unusable:

RULE 1 — MULTIPLE SCENES ALLOWED (1–3 max)
Extract up to 3 distinct major environments. If the chapter stays in one location, return only one. Never return more than 3.

RULE 2 — ENVIRONMENT MUST BE SPECIFIC
Never use vague descriptions like "a room" or "outside". Always name the exact location type and its defining visual qualities.
Wrong: "a dark room"
Right: "candlelit inn common room, rough timber walls, low ceiling, scattered wooden tables and benches, fireplace with dying embers"
Wrong: "a street"
Right: "narrow cobblestone alley, tall stone buildings pressing close on both sides, puddles reflecting dim lantern light, laundry lines overhead"

RULE 3 — TIME OF DAY AND LIGHTING ARE MANDATORY
Always include exact time of day: dawn, morning, midday, afternoon, dusk, evening, night, deep night.
Always include primary lighting source: candlelight, torchlight, fireplace glow, dim lanterns, overcast daylight, harsh midday sun, golden hour, moonlight, deep shadow.
These directly control the ComfyUI lighting setup.

RULE 4 — PURE BOORU TAGS ONLY
All tag fields use Danbooru-style comma-separated tags. No sentences. No prose. No "it is" or "there is".
Good: "cobblestone alley, dim lanterns, stone walls, puddles, night, cold blue shadow"
Bad: "It is a dark alley at night with some lanterns"

RULE 5 — ATMOSPHERE TAGS CAPTURE MOOD
atmosphere_tags must reflect the emotional register of the scene, not just the physical description.
Examples: "tense, shadowed, claustrophobic" / "warm, intimate, candlelit" / "desolate, windswept, melancholic" / "opulent, cold, formal"

RULE 6 — NO CHARACTER FACES IN SCENE IMAGES
Scene images are environment references. Characters appear only as silhouettes or background figures — never with identifiable faces.
List characters in characters_present using their exact name only. Their master_tags will be injected by the pipeline at low weight.

RULE 7 — WORLD CONSISTENCY
European-coded pre-industrial fantasy setting. Appropriate: stone, timber, cobblestone, iron, candles, torches, parchment, rough fabric.
Never: modern materials, neon, concrete, glass, electric lights, plastic, contemporary architecture, anachronistic technology.

RULE 8 — CAMERA PERSPECTIVE HINT
Always include exactly one: wide establishing shot, medium interior shot, low angle exterior, high angle overview, cramped interior close.

RULE 9 — SCENE NEGATIVE TAGS
Always include scene_negative. Always include at the end: realistic, photorealistic, 3d render, photograph, text, watermark, logo, ui elements, modern elements, character faces, portraits.

RULE 10 — scene_trigger MUST BE UNIQUE
scene_trigger is a snake_case identifier for future LoRA/embedding use.
Format: location_timeofday or location_mood. Examples: "candlelit_inn_night", "harbor_dusk", "castle_hall_cold"
Must be lowercase, underscores only, no spaces.

RULE 11 — palette IS MANDATORY
palette describes the dominant color palette of this scene in 4-6 color descriptors.
Examples: "warm amber, deep browns, muted reds, soft gold highlights" / "cold grey, pale blue, silver moonlight, deep black shadows"
This directly controls ComfyUI color generation.

Output ONLY a valid JSON array. No explanation, no code fences, no extra text before or after.
[
  {
    "scene_id": "chapter_001_inn_night",
    "scene_trigger": "candlelit_inn_night",
    "location_name": "Candlelit Inn Common Room",
    "environment_type": "interior/exterior/transitional",
    "time_of_day": "night",
    "lighting": "warm candlelight, fireplace glow, deep amber shadows",
    "palette": "warm amber, deep browns, muted reds, soft gold highlights",
    "description": "single factual paragraph describing the environment",
    "atmosphere_tags": "tense, shadowed, warm undertone, intimate",
    "environment_tags": "inn common room, rough timber walls, low ceiling, wooden tables, fireplace, candles, stone floor",
    "lighting_tags": "warm candlelight, deep amber, chiaroscuro, fireplace glow, long shadows",
    "camera_hint": "medium interior shot",
    "recurring_props": "heavy oak barrels, iron lantern hooks, scattered tankards",
    "characters_present": ["Leonardo", "Protagonist"],
    "scene_negative": "modern furniture, electric lighting, neon, concrete, glass, character faces, portraits, realistic, photorealistic, 3d render, photograph, text, watermark, logo, ui elements, modern elements"
  }
]"""

SCENE_EXTRACT_USER = """Extract all major scene environments from this chapter (1–3 maximum).

CHAPTER: {chapter_name}

TEXT:
{text}"""

SCENE_REFINE_SYSTEM = """You are merging multiple descriptions of the SAME recurring location across chapters into one definitive ComfyUI reference sheet.

RULES:

RULE 1 — FIRST APPEARANCE HAS PRIORITY
The first description is the most canonical. Use it as the base. Later descriptions only add detail or resolve gaps.

RULE 2 — RESOLVE CONFLICTS: explicit > most frequent > most detailed
Use the most common/default version of the location, not rare dramatic variants.

RULE 3 — palette AND atmosphere REPRESENT THE USUAL STATE
Use the palette and atmosphere that appear most often across descriptions, not the most dramatic version.

RULE 4 — recurring_props MUST BE COMPREHENSIVE
Combine all recurring_props from every description. Remove duplicates. Only keep props that appear in 2+ descriptions.

RULE 5 — scene_negative MUST BE COMPREHENSIVE
Combine ALL scene_negative tags from every description. Remove duplicates. Always include at the end: realistic, photorealistic, 3d render, photograph, text, watermark, logo, ui elements, modern elements, character faces, portraits.

RULE 6 — NEVER INVENT
Only merge what exists across the provided descriptions.

Output ONLY a single valid JSON object. No explanation, no code fences, no extra text.
{
  "scene_id": "...",
  "scene_trigger": "...",
  "location_name": "...",
  "environment_type": "...",
  "time_of_day": "...",
  "lighting": "...",
  "palette": "...",
  "description": "...",
  "atmosphere_tags": "...",
  "environment_tags": "...",
  "lighting_tags": "...",
  "camera_hint": "...",
  "recurring_props": "...",
  "characters_present": [],
  "scene_negative": "..."
}"""

SCENE_REFINE_USER = """Merge these descriptions of the same location "{location_name}" into one definitive reference.

Descriptions:
{descriptions}"""


def extract_scenes(chapter_text: str, chapter_name: str = "",
                   novel_dir: str = "") -> list[dict]:
    """Extract 1-3 major scenes from a chapter. Returns empty list on failure."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from video.soul_parser import build_soul_context

    soul_context = build_soul_context(novel_dir, ["lighting_palette", "world_aesthetic", "avoid"]) if novel_dir else ""
    system_prompt = SCENE_EXTRACT_SYSTEM
    if soul_context:
        system_prompt = soul_context + "\n\n" + SCENE_EXTRACT_SYSTEM

    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": SCENE_EXTRACT_USER.format(
                    chapter_name=chapter_name,
                    text=chapter_text[:4000]
                )},
            ],
            temperature=0.2,
            max_tokens=1200,
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
        scenes = json.loads(raw[start:end])
        return scenes[:3]  # enforce max 3
    except Exception:
        return []


def refine_location(location_name: str, descriptions: list[dict]) -> dict | None:
    """Merge multiple descriptions of the same recurring location."""
    if len(descriptions) == 1:
        return descriptions[0]
    desc_text = "\n---\n".join([
        json.dumps(d, ensure_ascii=False, indent=2) for d in descriptions
    ])
    try:
        resp = client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=[
                {"role": "system", "content": SCENE_REFINE_SYSTEM},
                {"role": "user", "content": SCENE_REFINE_USER.format(
                    location_name=location_name,
                    descriptions=desc_text
                )},
            ],
            temperature=0.1,
            max_tokens=700,
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
        return json.loads(raw[start:end])
    except Exception:
        return None


def build_scene_prompt(scene: dict, characters: list[dict] | None = None,
                       art_style: str = "") -> tuple[str, str]:
    """
    Build ComfyUI positive + negative prompts from a scene dict.
    Injects character master_tags at 0.4 weight as silhouettes for characters_present.
    Prompt order: environment → lighting → palette → atmosphere → camera → props → char silhouettes → style → quality
    """
    from images.prompts import ANIME_QUALITY_TAGS, _current_art_style

    style = art_style or _current_art_style

    env_tags = scene.get("environment_tags", "")
    lighting_tags = scene.get("lighting_tags", "")
    palette = scene.get("palette", "")
    atmosphere = scene.get("atmosphere_tags", "")
    camera = scene.get("camera_hint", "wide establishing shot")
    props = scene.get("recurring_props", "")

    # Inject character silhouettes at low weight
    char_silhouette = ""
    if characters and scene.get("characters_present"):
        present_names = {n.lower() for n in scene.get("characters_present", [])}
        char_lookup = {c.get("name", "").lower(): c for c in characters}
        silhouettes = []
        for name in present_names:
            char = char_lookup.get(name)
            if char and char.get("master_tags"):
                silhouettes.append(f"silhouette of ({char['master_tags']}:0.4)")
        if silhouettes:
            char_silhouette = ", ".join(silhouettes) + ", background figures only, no faces"

    positive_parts = [
        env_tags,
        lighting_tags,
        palette,
        atmosphere,
        camera,
        props,
        char_silhouette,
        "highly detailed background, atmospheric lighting, depth and perspective",
        "painterly anime background art, richly detailed environment",
        style,
        ANIME_QUALITY_TAGS,
    ]
    positive = ", ".join(p for p in positive_parts if p)
    negative = scene.get(
        "scene_negative",
        "realistic, photorealistic, 3d render, photograph, text, watermark, logo, character faces, portraits, modern elements"
    )

    return positive, negative
