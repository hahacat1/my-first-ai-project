"""
Builds Stable Diffusion prompts for character portraits and scene images.
Uses anime-style phrasing optimized for Anything V5 / CounterfeitXL models.
"""

ANIME_QUALITY_TAGS = (
    "masterpiece, best quality, highres, ultra-detailed, "
    "anime style, 2D illustration, vibrant colors"
)

NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, missing fingers, extra digit, fewer digits, "
    "cropped, worst quality, low quality, jpeg artifacts, signature, watermark, "
    "username, blurry, artist name, 3D, realistic, photographic"
)


def character_portrait_prompt(character: dict) -> tuple[str, str]:
    """Returns (positive_prompt, negative_prompt) for a character portrait."""
    desc = character.get("description", "")
    name = character.get("name", "character")

    positive = (
        f"{ANIME_QUALITY_TAGS}, "
        f"portrait of {desc}, "
        f"looking at viewer, neutral expression, "
        f"white background, full body visible, character sheet"
    )
    return positive, NEGATIVE_PROMPT


def scene_image_prompt(scene_text: str, characters_in_scene: list[str] = None) -> tuple[str, str]:
    """Returns (positive_prompt, negative_prompt) for a scene illustration."""
    chars_tag = ""
    if characters_in_scene:
        chars_tag = ", ".join(characters_in_scene[:2])  # max 2 chars per scene

    # Truncate scene text for context
    context = scene_text[:300].replace("\n", " ")

    positive = (
        f"{ANIME_QUALITY_TAGS}, "
        f"{'with ' + chars_tag + ', ' if chars_tag else ''}"
        f"dynamic scene, detailed background, cinematic composition, "
        f"atmospheric lighting, {context[:100]}"
    )
    return positive, NEGATIVE_PROMPT
