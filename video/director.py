"""
Uses Ollama to write movie-director style prompts for each video segment.
These prompts feed into Higgsfield's image-to-video generator.
"""

import os
import json
import ollama
from pipeline.config import OLLAMA_MODEL

DIRECTOR_PROMPT = """You are a visionary anime film director creating a cinematic adaptation
of a Korean web novel. Your job is to write a single image-to-video generation prompt
for the following scene.

Rules:
- Write ONE prompt only, max 2 sentences
- Use cinematic camera language: "slow push-in", "wide establishing shot", "over-the-shoulder",
  "low angle", "Dutch tilt", "dolly zoom", "aerial pan"
- Include lighting: "golden hour", "neon-lit", "moonlit", "dramatic chiaroscuro", "soft diffused"
- Include emotion/atmosphere: "tense anticipation", "melancholic solitude", "triumphant energy"
- End with: "anime style, cinematic, 4K, fluid motion"
- Do NOT describe text or subtitles
- Do NOT reference "the novel" or "the story"

SCENE TEXT (first 400 words):
{scene_text}

Write the director prompt now:"""


def write_director_prompts(segments: list[dict], scenes_dir: str) -> list[dict]:
    """
    For each segment, generate a director-style video prompt using Ollama.
    Returns segments with added 'director_prompt' field.
    Saves prompts to scenes_dir/prompts.json for review/editing.
    """
    os.makedirs(scenes_dir, exist_ok=True)
    prompts_file = os.path.join(scenes_dir, "director_prompts.json")

    # Load existing prompts if we're resuming
    existing = {}
    if os.path.exists(prompts_file):
        with open(prompts_file) as f:
            existing = {p["id"]: p["director_prompt"] for p in json.load(f)}

    results = []
    print(f"  Writing director prompts for {len(segments)} segments...")

    for i, seg in enumerate(segments, 1):
        if seg["id"] in existing:
            seg["director_prompt"] = existing[seg["id"]]
            print(f"  [{i}/{len(segments)}] {seg['id']} (cached)")
            results.append(seg)
            continue

        scene_excerpt = " ".join(seg["text"].split()[:400])
        print(f"  [{i}/{len(segments)}] {seg['id']}...", end=" ", flush=True)

        try:
            resp = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{
                    "role": "user",
                    "content": DIRECTOR_PROMPT.format(scene_text=scene_excerpt)
                }],
                options={"temperature": 0.7},
            )
            prompt_text = resp["message"]["content"].strip()
            # Strip any thinking tags if model uses them
            if "<think>" in prompt_text:
                prompt_text = prompt_text.split("</think>")[-1].strip()
            seg["director_prompt"] = prompt_text
            print(f"done")
        except Exception as e:
            seg["director_prompt"] = f"Dynamic anime scene, fluid motion, cinematic lighting, anime style, 4K"
            print(f"fallback ({e})")

        results.append(seg)

    # Save all prompts for user to review / edit before video generation
    with open(prompts_file, "w", encoding="utf-8") as f:
        json.dump([{"id": s["id"], "chapters": s["chapters"],
                    "director_prompt": s["director_prompt"]} for s in results],
                  f, indent=2, ensure_ascii=False)

    print(f"  Prompts saved to: {prompts_file}")
    print(f"  TIP: Open director_prompts.json to review/edit prompts before video generation!")
    return results
