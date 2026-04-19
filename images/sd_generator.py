"""
Generates images via ComfyUI's REST API (local Stable Diffusion).

Setup required (one-time):
1. Install ComfyUI: https://github.com/comfyanonymous/ComfyUI
2. Download anime model: Anything V5 or CounterfeitXL
   - Place .safetensors file in ComfyUI/models/checkpoints/
3. Launch ComfyUI: python main.py --port 8188
4. Then run this pipeline stage.
"""

import os
import json
import time
import uuid
import requests
from images.prompts import character_portrait_prompt, scene_image_prompt, NEGATIVE_PROMPT
from pipeline.config import COMFYUI_URL


# Minimal ComfyUI workflow for image generation
def _build_workflow(positive: str, negative: str, width: int = 832, height: int = 1216) -> dict:
    """Returns a ComfyUI API workflow dict."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(uuid.uuid4().int % 2**32),
                "steps": 28,
                "cfg": 7,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "AnythingV5.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "pipeline_", "images": ["8", 0]},
        },
    }


def _is_comfyui_running() -> bool:
    try:
        requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        return True
    except Exception:
        return False


def _generate_image(positive: str, negative: str, out_path: str,
                    width: int = 832, height: int = 1216) -> None:
    if not _is_comfyui_running():
        raise RuntimeError(
            "ComfyUI is not running. Start it with:\n"
            "  cd /path/to/ComfyUI && python main.py --port 8188\n"
            "See: https://github.com/comfyanonymous/ComfyUI"
        )

    workflow = _build_workflow(positive, negative, width, height)
    client_id = str(uuid.uuid4())

    # Queue the prompt
    resp = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    # Poll until done
    for _ in range(120):  # max 2 minutes
        time.sleep(1)
        history = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10).json()
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images", [])
                if images:
                    img_info = images[0]
                    img_resp = requests.get(
                        f"{COMFYUI_URL}/view",
                        params={"filename": img_info["filename"], "type": img_info["type"]},
                        timeout=30,
                    )
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    return
            break

    raise RuntimeError(f"ComfyUI did not return an image for: {out_path}")


def generate_character_portraits(characters: list, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    print(f"  Generating {len(characters)} character portraits → {out_dir}")

    for char in characters:
        name_slug = char["name"].lower().replace(" ", "_")
        out_path = os.path.join(out_dir, f"{name_slug}.png")
        if os.path.exists(out_path):
            print(f"    {char['name']} already exists, skipping")
            continue

        positive, negative = character_portrait_prompt(char)
        print(f"    Generating {char['name']}...", end=" ", flush=True)
        try:
            _generate_image(positive, negative, out_path, width=832, height=1216)
            print("done")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            continue


def generate_scene_images(proofread_dir: str, out_dir: str) -> None:
    """Generate one scene image per chapter (first segment of each chapter)."""
    os.makedirs(out_dir, exist_ok=True)

    chapters = sorted([
        f for f in os.listdir(proofread_dir)
        if (f.startswith("chapter-") or f.startswith("Chapter ")) and f.endswith(".txt")
    ])
    print(f"  Generating scene images for {len(chapters)} chapters → {out_dir}")

    for ch in chapters:
        img_name = ch.replace(".txt", ".png")
        out_path = os.path.join(out_dir, img_name)
        if os.path.exists(out_path):
            continue

        with open(os.path.join(proofread_dir, ch), encoding="utf-8") as f:
            text = f.read()

        positive, negative = scene_image_prompt(text[:500])
        print(f"    {ch}...", end=" ", flush=True)
        try:
            _generate_image(positive, negative, out_path, width=1216, height=832)
            print("done")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            continue
