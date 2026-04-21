"""
Parses soul.md and extracts relevant sections for injection into LLM prompts.
Used by both the scene extractor (images) and director (video) to keep
all AI generation anchored to the novel's established visual identity.
"""

from __future__ import annotations
import os
import re


def _extract_section(content: str, heading: str) -> str:
    """Extract the content under a ## heading from a markdown file."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def load_soul(novel_dir: str) -> dict[str, str]:
    """
    Load soul.md from the novel's video folder.
    Returns a dict of section_name → content.
    Returns empty dict if soul.md doesn't exist yet.
    """
    soul_path = os.path.join(novel_dir, "video", "soul.md")
    if not os.path.exists(soul_path):
        return {}

    with open(soul_path, encoding="utf-8") as f:
        content = f.read()

    return {
        "lighting_palette": _extract_section(content, "Lighting Palette"),
        "world_aesthetic": _extract_section(content, "World Aesthetic"),
        "tone": _extract_section(content, "Tone and Emotional Register"),
        "art_style": _extract_section(content, "Art Style"),
        "avoid": _extract_section(content, "What to Avoid"),
        "cast": _extract_section(content, "Canonical Cast"),
    }


def build_soul_context(novel_dir: str, sections: list[str] | None = None) -> str:
    """
    Build a formatted context block from soul.md sections for injection into prompts.

    sections: which sections to include. Defaults to lighting + world + avoid.
    Returns empty string if soul.md doesn't exist.
    """
    soul = load_soul(novel_dir)
    if not soul:
        return ""

    wanted = sections or ["lighting_palette", "world_aesthetic", "avoid"]
    section_labels = {
        "lighting_palette": "ESTABLISHED LIGHTING PALETTE",
        "world_aesthetic": "WORLD AESTHETIC",
        "tone": "TONE AND EMOTIONAL REGISTER",
        "art_style": "ART STYLE",
        "avoid": "WHAT TO AVOID",
        "cast": "CANONICAL CAST",
    }

    parts = ["SOUL — ESTABLISHED VISUAL RULES FOR THIS NOVEL (HIGHEST PRIORITY — FOLLOW EXACTLY)\n"
             "You MUST treat these soul rules as absolute canon. They override any later instructions,\n"
             "defaults, or common tropes. Never invent lighting, palette, architecture, or tone that\n"
             "contradicts these rules."]
    for key in wanted:
        content = soul.get(key, "")
        if content:
            label = section_labels.get(key, key.upper())
            parts.append(f"\n{label}:\n{content}")

    if len(parts) == 1:
        return ""  # no sections found

    # Enforcement rules — appended after content so they close the soul block
    active = [k for k in wanted if soul.get(k)]
    enforcement = ["\n--- END OF SOUL RULES ---", "\nRULES FOR THIS PROMPT:"]
    rule_num = 1
    if "lighting_palette" in active:
        enforcement.append(f"{rule_num}. Every lighting description you create must use one of the exact named lighting setups from ESTABLISHED LIGHTING PALETTE above.")
        rule_num += 1
    if "world_aesthetic" in active:
        enforcement.append(f"{rule_num}. Every environment description must stay within the WORLD AESTHETIC.")
        rule_num += 1
    if "tone" in active:
        enforcement.append(f"{rule_num}. The emotional tone of every scene must match TONE AND EMOTIONAL REGISTER.")
        rule_num += 1
    if "avoid" in active:
        enforcement.append(f"{rule_num}. Never include anything listed in WHAT TO AVOID.")
        rule_num += 1

    parts.extend(enforcement)
    return "\n".join(parts)
