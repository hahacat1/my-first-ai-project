"""
Builds Stable Diffusion prompts for character portraits and scene images.
Optimized for dreamlike-anime model with per-novel art style support.
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

# Default art style — overridden per novel via config art_style field
DEFAULT_ART_STYLE = (
    "anime style, vibrant colors, dynamic composition"
)

# Novel art style is injected at runtime via set_novel_style()
_current_art_style = DEFAULT_ART_STYLE


def set_novel_style(art_style: str):
    """Call this before generating images to apply the novel's visual tone."""
    global _current_art_style
    _current_art_style = art_style


def character_portrait_prompt(character: dict) -> tuple[str, str]:
    """Returns (positive_prompt, negative_prompt) for a character portrait."""
    desc = character.get("description", "")
    tags = character.get("tags", "")
    role = character.get("role", "supporting")

    role_style = {
        "protagonist": "confident posture, determined expression, hero aura",
        "antagonist": "cold piercing gaze, intimidating presence, dark elegance",
        "supporting": "expressive face, natural relaxed posture, warm presence",
        "minor": "natural expression, casual stance",
    }.get(role, "natural expression")

    positive = (
        f"{ANIME_QUALITY_TAGS}, "
        f"{_current_art_style}, "
        f"{tags + ', ' if tags else ''}"
        f"{desc}, "
        f"{role_style}, "
        f"looking at viewer, "
        f"white background, full body character sheet, "
        f"front view, consistent design, "
        f"{PORTRAIT_LIGHTING}"
    )
    return positive, NEGATIVE_PROMPT


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
