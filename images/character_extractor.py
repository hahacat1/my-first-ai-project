"""
Uses Ollama to read proofread chapters and extract character appearance descriptions.
Only scans first 20 chapters — characters are usually introduced early.
"""

import os
import json
import ollama
from pipeline.config import OLLAMA_MODEL

PROMPT = """You are reading a Korean web novel translated into English.

Read the following text and list every named character mentioned, with their physical appearance.
For each character include: name, gender, age (approximate), hair color, eye color, clothing style,
body type, and any notable features.

Format your response as a JSON array like this:
[
  {{
    "name": "Character Name",
    "description": "young woman, mid-20s, long black hair, sharp red eyes, slim build, wears dark robes, elegant"
  }}
]

Only include characters with clear physical descriptions. If a character has no physical description, skip them.
Return ONLY the JSON array, no other text.

TEXT:
{text}"""


def extract_characters(proofread_dir: str, seed_characters: list = None) -> list:
    """
    Scan the first 20 chapters and extract all character descriptions.
    Merges with seed_characters from config if provided.
    """
    chapters = sorted([
        f for f in os.listdir(proofread_dir)
        if f.startswith("chapter-") and f.endswith(".txt")
    ])[:20]

    combined_text = ""
    for ch in chapters:
        with open(os.path.join(proofread_dir, ch), encoding="utf-8") as f:
            combined_text += f.read() + "\n\n"

    # Send in 3000-word chunks to stay within context
    words = combined_text.split()
    chunk_size = 3000
    all_characters = {}

    for start in range(0, min(len(words), 30000), chunk_size):
        chunk = " ".join(words[start:start + chunk_size])
        try:
            resp = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": PROMPT.format(text=chunk)}],
                options={"temperature": 0.1},
            )
            raw = resp["message"]["content"].strip()
            # Extract JSON even if wrapped in markdown
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            chars = json.loads(raw)
            for c in chars:
                name = c.get("name", "").strip()
                if name and name not in all_characters:
                    all_characters[name] = c
        except Exception:
            continue  # skip malformed chunks

    result = list(all_characters.values())

    # Merge seed characters from config (they take priority)
    if seed_characters:
        seed_names = {c["name"] for c in seed_characters}
        result = [c for c in result if c["name"] not in seed_names]
        result = seed_characters + result

    # Save extracted characters for reference
    out_path = os.path.join(os.path.dirname(proofread_dir), "characters.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Characters saved to: {out_path}")

    return result
