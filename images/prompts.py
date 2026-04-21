"""
Builds Stable Diffusion prompts for character portraits and scene images.
Optimized for AnimagineXL with per-novel art style support.

Prompt order (controls SD weight priority):
  character appearance → clothing → art style → quality → lighting
"""

ANIME_QUALITY_TAGS = (
    "masterpiece, best quality, highres, ultra-detailed, intricate details, "
    "anime style, 2D illustration, vibrant colors, sharp lineart, "
    "professional illustration, official art quality"
)

PORTRAIT_LIGHTING = (
    "soft rim lighting, dramatic side lighting, subsurface scattering on skin, "
    "depth of field, bokeh background, cinematic framing"
)

NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, missing fingers, extra digit, fewer digits, "
    "extra limbs, fused fingers, too many fingers, long neck, "
    "cropped, worst quality, low quality, jpeg artifacts, signature, watermark, "
    "username, blurry, artist name, 3D, realistic, photographic, "
    "deformed, disfigured, mutated, ugly, bad proportions, "
    "out of frame, poorly drawn face, cloned face, gross proportions"
)

SCENE_NEGATIVE = NEGATIVE_PROMPT + (
    ", no characters, empty scene, text, logo, ui elements"
)

DEFAULT_ART_STYLE = "anime style, vibrant colors, dynamic composition"

_current_art_style = DEFAULT_ART_STYLE


def set_novel_style(art_style: str):
    global _current_art_style
    _current_art_style = art_style


def character_portrait_prompt(character: dict) -> tuple[str, str]:
    """Returns (positive_prompt, negative_prompt) for a character portrait.

    Priority order: appearance → clothing → style → quality → lighting
    Character-specific details always come before global style tags.
    """
    desc = character.get("description", "")
    tags = character.get("tags", "")
    clothing = character.get("clothing", "")
    eye_color = character.get("eye_color", "")
    role = character.get("role", "supporting")

    role_style = {
        "protagonist": "natural relaxed posture, soft determined expression",
        "antagonist": "cold composed posture, controlled expression",
        "supporting": "expressive face, natural relaxed posture, warm presence",
        "minor": "natural expression, casual stance",
    }.get(role, "natural expression")

    # master_tags is the single source of truth — use it if available
    # Fall back to assembling from parts for seed/manual characters
    master_tags = character.get("master_tags", "")
    if master_tags:
        appearance = master_tags
    else:
        appearance_parts = []
        if desc:
            appearance_parts.append(desc)
        if eye_color:
            appearance_parts.append(eye_color)
        if clothing:
            appearance_parts.append(clothing)
        if tags:
            appearance_parts.append(tags)
        appearance = ", ".join(filter(None, appearance_parts))

    positive = (
        f"{appearance}, "
        f"{role_style}, "
        f"looking at viewer, white background, full body character sheet, "
        f"front view, consistent design, "
        f"{_current_art_style}, "
        f"{ANIME_QUALITY_TAGS}, "
        f"{PORTRAIT_LIGHTING}"
    )

    # Character-specific negative — block wrong clothing types if defined
    clothing_neg = character.get("clothing_negative", "")
    negative = NEGATIVE_PROMPT
    if clothing_neg:
        negative = negative + f", {clothing_neg}"

    return positive, negative


def scene_image_prompt(scene_text: str, characters_in_scene: list[str] = None) -> tuple[str, str]:
    """Returns (positive_prompt, negative_prompt) for a scene illustration."""
    chars_tag = ""
    if characters_in_scene:
        chars_tag = ", ".join(characters_in_scene[:2])

    context = scene_text[:300].replace("\n", " ").strip()

    positive = (
        f"{ANIME_QUALITY_TAGS}, "
        f"{_current_art_style}, "
        f"{'with ' + chars_tag + ', ' if chars_tag else ''}"
        f"highly detailed background, atmospheric lighting, "
        f"depth and perspective, richly detailed environment, "
        f"painterly anime background art, "
        f"{context[:150]}"
    )
    return positive, SCENE_NEGATIVE
