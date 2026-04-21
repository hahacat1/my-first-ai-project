from __future__ import annotations

"""
Generates images via ComfyUI's REST API (local Stable Diffusion).

Setup required (one-time):
1. Install ComfyUI: https://github.com/comfyanonymous/ComfyUI
2. Download model — recommended: AnimagineXL 4.0 (SDXL, best anime quality)
   - Place .safetensors in ComfyUI/models/checkpoints/
   - Update SD_CHECKPOINT in pipeline/config.py
3. Download VAE: vae-ft-mse-840000-ema-pruned.safetensors
   - Place in ComfyUI/models/vae/  (fixes washed-out colors)
4. (Optional) IP-Adapter FaceID for face consistency:
   - Install: https://github.com/cubiq/ComfyUI_IPAdapter_plus
   - pip install insightface onnxruntime  (in ComfyUI's Python env)
   - Download ip-adapter-faceid-plusv2_sd15.bin → ComfyUI/models/ipadapter/
   - For AnimagineXL (SDXL): use ip-adapter-faceid-plusv2_sdxl.bin instead
5. (Optional) Real-ESRGAN for post-generation upscale:
   - Download realesrgan-ncnn-vulkan binary
   - Set REALESRGAN_BIN in .env or pipeline/config.py
6. Launch ComfyUI: python main.py --port 8188
"""

import os
import json
import time
import uuid
import shutil
import subprocess
import requests
from images.prompts import character_portrait_prompt, scene_image_prompt, NEGATIVE_PROMPT
from pipeline.config import (
    COMFYUI_URL,
    SD_CHECKPOINT, SD_VAE,
    SD_SAMPLER, SD_SCHEDULER, SD_STEPS, SD_CFG,
    SD_PORTRAIT_W, SD_PORTRAIT_H,
    SD_HIRES_SCALE, SD_HIRES_DENOISE, SD_HIRES_STEPS,
    SD_IPADAPTER_MODEL, SD_FACE_WEIGHT,
    SD_CONTROLNET_MODEL, SD_CONTROLNET_STRENGTH,
    REALESRGAN_BIN,
)

POSE_REF_DIR = os.path.join(os.path.dirname(__file__), "pose_refs")


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def _clip_node(clip_source: list) -> dict:
    """CLIPSetLastLayer at stop=-2 (clip skip 2). Improves anime style adherence."""
    return {
        "class_type": "CLIPSetLastLayer",
        "inputs": {"clip": clip_source, "stop_at_clip_layer": -2},
    }


def _controlnet_nodes(pose_image: str, positive_src: list, negative_src: list,
                      model_src: list) -> tuple[dict, list, list, list]:
    """
    Returns (nodes_dict, conditioned_positive, conditioned_negative, conditioned_model).
    Silently skips if ControlNet model file is missing.
    """
    cn_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ComfyUI", "models", "controlnet", SD_CONTROLNET_MODEL,
    )
    # Resolve relative to ComfyUI install
    comfyui_cn = os.path.expanduser(f"~/Desktop/ComfyUI/models/controlnet/{SD_CONTROLNET_MODEL}")
    if not os.path.exists(comfyui_cn):
        return {}, positive_src, negative_src, model_src

    nodes = {
        "20": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": SD_CONTROLNET_MODEL}},
        "21": {"class_type": "LoadImage", "inputs": {"image": pose_image}},
        "22": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": positive_src,
                "negative": negative_src,
                "control_net": ["20", 0],
                "image": ["21", 0],
                "strength": SD_CONTROLNET_STRENGTH,
                "start_percent": 0.0,
                "end_percent": 0.85,
            },
        },
    }
    return nodes, ["22", 0], ["22", 1], model_src


def _build_workflow(positive: str, negative: str,
                    width: int = SD_PORTRAIT_W, height: int = SD_PORTRAIT_H,
                    pose_image: str | None = None) -> dict:
    """Standard workflow: checkpoint → clip skip 2 → ControlNet → VAE → hires fix → save."""
    use_vae = bool(SD_VAE)
    hires = SD_HIRES_SCALE > 1.0

    wf: dict = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD_CHECKPOINT}},
        "2": _clip_node(["1", 1]),
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
    }

    pos_src, neg_src, model_src = ["3", 0], ["4", 0], ["1", 0]
    if pose_image:
        cn_nodes, pos_src, neg_src, model_src = _controlnet_nodes(
            pose_image, pos_src, neg_src, model_src)
        wf.update(cn_nodes)

    wf["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": int(uuid.uuid4().int % 2**32),
            "steps": SD_STEPS, "cfg": SD_CFG,
            "sampler_name": SD_SAMPLER, "scheduler": SD_SCHEDULER,
            "denoise": 1.0,
            "model": model_src, "positive": pos_src,
            "negative": neg_src, "latent_image": ["5", 0],
        },
    }

    if use_vae:
        wf["7"] = {"class_type": "VAELoader", "inputs": {"vae_name": SD_VAE}}
        vae_src = ["7", 0]
    else:
        vae_src = ["1", 2]

    if hires:
        target_w, target_h = int(width * SD_HIRES_SCALE), int(height * SD_HIRES_SCALE)
        wf["8"] = {"class_type": "LatentUpscale",
                   "inputs": {"upscale_method": "nearest-exact", "width": target_w,
                              "height": target_h, "crop": "disabled", "samples": ["6", 0]}}
        wf["9"] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(uuid.uuid4().int % 2**32),
                "steps": SD_HIRES_STEPS, "cfg": SD_CFG,
                "sampler_name": SD_SAMPLER, "scheduler": SD_SCHEDULER,
                "denoise": SD_HIRES_DENOISE,
                "model": ["1", 0], "positive": pos_src,
                "negative": neg_src, "latent_image": ["8", 0],
            },
        }
        decode_src = ["9", 0]
    else:
        decode_src = ["6", 0]

    wf["10"] = {"class_type": "VAEDecode", "inputs": {"samples": decode_src, "vae": vae_src}}
    wf["11"] = {"class_type": "SaveImage",
                "inputs": {"filename_prefix": "pipeline_", "images": ["10", 0]}}
    return wf


def _build_faceid_workflow(positive: str, negative: str,
                            ref_image_name: str,
                            width: int = SD_PORTRAIT_W, height: int = SD_PORTRAIT_H,
                            face_weight: float = SD_FACE_WEIGHT,
                            pose_image: str | None = None) -> dict:
    """FaceID + ControlNet workflow. Falls back to standard workflow if IPAdapter missing."""
    use_vae = bool(SD_VAE)
    hires = SD_HIRES_SCALE > 1.0

    wf: dict = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD_CHECKPOINT}},
        "2": _clip_node(["1", 1]),
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "12": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": SD_IPADAPTER_MODEL}},
        "13": {"class_type": "InsightFaceLoader", "inputs": {"provider": "CPU"}},
        "14": {"class_type": "LoadImage", "inputs": {"image": ref_image_name}},
        "15": {
            "class_type": "IPAdapterFaceID",
            "inputs": {
                "model": ["1", 0], "ipadapter": ["12", 0],
                "image": ["14", 0], "insightface": ["13", 0],
                "weight": face_weight, "weight_faceidv2": 1.0,
                "weight_type": "linear", "combine_embeds": "concat",
                "start_at": 0.0, "end_at": 1.0,
            },
        },
    }

    pos_src, neg_src, model_src = ["3", 0], ["4", 0], ["15", 0]
    if pose_image:
        cn_nodes, pos_src, neg_src, model_src = _controlnet_nodes(
            pose_image, pos_src, neg_src, model_src)
        wf.update(cn_nodes)

    wf["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": int(uuid.uuid4().int % 2**32),
            "steps": SD_STEPS, "cfg": SD_CFG,
            "sampler_name": SD_SAMPLER, "scheduler": SD_SCHEDULER,
            "denoise": 1.0,
            "model": model_src, "positive": pos_src,
            "negative": neg_src, "latent_image": ["5", 0],
        },
    }

    if use_vae:
        wf["7"] = {"class_type": "VAELoader", "inputs": {"vae_name": SD_VAE}}
        vae_src = ["7", 0]
    else:
        vae_src = ["1", 2]

    if hires:
        target_w, target_h = int(width * SD_HIRES_SCALE), int(height * SD_HIRES_SCALE)
        wf["8"] = {"class_type": "LatentUpscale",
                   "inputs": {"upscale_method": "nearest-exact", "width": target_w,
                              "height": target_h, "crop": "disabled", "samples": ["6", 0]}}
        wf["9"] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(uuid.uuid4().int % 2**32),
                "steps": SD_HIRES_STEPS, "cfg": SD_CFG,
                "sampler_name": SD_SAMPLER, "scheduler": SD_SCHEDULER,
                "denoise": SD_HIRES_DENOISE,
                "model": ["15", 0], "positive": pos_src,
                "negative": neg_src, "latent_image": ["8", 0],
            },
        }
        decode_src = ["9", 0]
    else:
        decode_src = ["6", 0]

    wf["10"] = {"class_type": "VAEDecode", "inputs": {"samples": decode_src, "vae": vae_src}}
    wf["11"] = {"class_type": "SaveImage",
                "inputs": {"filename_prefix": "pipeline_faceid_", "images": ["10", 0]}}
    return wf


# ---------------------------------------------------------------------------
# ComfyUI helpers
# ---------------------------------------------------------------------------

def _is_comfyui_running() -> bool:
    try:
        requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        return True
    except Exception:
        return False


def _check_ipadapter_available() -> bool:
    try:
        resp = requests.get(f"{COMFYUI_URL}/object_info/IPAdapterFaceID", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _upload_to_comfy_input(image_path: str) -> str:
    """Upload a local image to ComfyUI's input folder. Returns assigned filename."""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{COMFYUI_URL}/upload/image",
            files={"image": (os.path.basename(image_path), f, "image/png")},
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()["name"]


def _run_workflow(workflow: dict, out_path: str) -> None:
    """Submit workflow to ComfyUI, poll until done, save result to out_path."""
    client_id = str(uuid.uuid4())
    resp = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    for _ in range(720):  # up to 12 min (hires fix at 1.5× needs ~8 min on MPS)
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


def _upscale_realesrgan(image_path: str) -> None:
    """
    Run Real-ESRGAN 2× upscale on image_path in-place.
    Skips silently if binary not found or upscale fails.
    """
    if not REALESRGAN_BIN:
        return
    binary = shutil.which(REALESRGAN_BIN) or REALESRGAN_BIN
    if not shutil.which(binary):
        return
    tmp = image_path + ".upscaled.png"
    try:
        subprocess.run(
            [binary, "-i", image_path, "-o", tmp, "-n", "realesrgan-x4plus-anime", "-s", "2"],
            check=True, capture_output=True, timeout=120,
        )
        os.replace(tmp, image_path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Main generation entry points
# ---------------------------------------------------------------------------

def _generate_image(positive: str, negative: str, out_path: str,
                    width: int = SD_PORTRAIT_W, height: int = SD_PORTRAIT_H,
                    face_ref_path: str | None = None,
                    pose_image: str | None = None) -> None:
    """
    Generate one image via ComfyUI. Applies clip skip 2, explicit VAE, hires fix.
    face_ref_path: optional portrait for IP-Adapter FaceID — gracefully falls back.
    pose_image: optional OpenPose skeleton for ControlNet pose guidance.
    """
    if not _is_comfyui_running():
        raise RuntimeError(
            "ComfyUI is not running. Start it with:\n"
            "  cd /path/to/ComfyUI && python main.py --port 8188"
        )

    # Upload pose image to ComfyUI input dir if provided
    pose_name = None
    if pose_image and os.path.exists(pose_image):
        try:
            pose_name = _upload_to_comfy_input(pose_image)
        except Exception:
            pose_name = None

    if face_ref_path and os.path.exists(face_ref_path) and _check_ipadapter_available():
        try:
            ref_name = _upload_to_comfy_input(face_ref_path)
            workflow = _build_faceid_workflow(positive, negative, ref_name,
                                              width, height, pose_image=pose_name)
            _run_workflow(workflow, out_path)
            return
        except Exception as e:
            print(f"[FaceID failed: {e}, using standard]", end=" ", flush=True)

    workflow = _build_workflow(positive, negative, width, height, pose_image=pose_name)
    _run_workflow(workflow, out_path)


def _parse_prompt_section(content: str, section: str) -> str:
    """Extract a [SECTION] block from a prompt.txt file."""
    marker = f"[{section}]"
    if marker not in content:
        return ""
    after = content.split(marker, 1)[1]
    end = after.find("\n[")
    return after[:end].strip() if end != -1 else after.strip()


def generate_character_portraits(characters: list, out_dir: str,
                                  force: bool = False) -> None:
    """
    Generate portrait(s) for each character.

    Produces two images per character:
      portrait.png      — front view (primary, used by downstream pipeline)
      portrait_34.png   — three-quarter view (bonus reference for DomoAI)

    force=True: regenerate even if portrait.png exists, using it as FaceID reference
    to preserve face identity while allowing prompt improvements.
    """
    os.makedirs(out_dir, exist_ok=True)
    print(f"  Generating {len(characters)} character portraits → {out_dir}")
    hires_note = f" + hires {SD_HIRES_SCALE}×" if SD_HIRES_SCALE > 1.0 else ""
    print(f"  Settings: {SD_CHECKPOINT} | {SD_SAMPLER}/{SD_SCHEDULER} "
          f"steps={SD_STEPS} cfg={SD_CFG}{hires_note}")

    for char in characters:
        name_slug = char["name"].lower().replace(" ", "_").replace("/", "_")
        char_dir = os.path.join(out_dir, name_slug)
        os.makedirs(char_dir, exist_ok=True)
        out_path = os.path.join(char_dir, "portrait.png")
        out_34_path = os.path.join(char_dir, "portrait_34.png")

        if os.path.exists(out_path) and not force:
            print(f"    {char['name']} — exists, skipping")
            continue

        prompt_path = os.path.join(char_dir, "prompt.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, encoding="utf-8") as f:
                content = f.read()
            positive = _parse_prompt_section(content, "POSITIVE PROMPT")
            negative = _parse_prompt_section(content, "NEGATIVE PROMPT") or NEGATIVE_PROMPT
        else:
            positive, negative = character_portrait_prompt(char)

        face_ref = out_path if (force and os.path.exists(out_path)) else None
        faceid_tag = " [FaceID]" if face_ref else ""

        pose_front = os.path.join(POSE_REF_DIR, "front.png")
        pose_34 = os.path.join(POSE_REF_DIR, "three_quarter.png")

        # — Front view (portrait.png)
        print(f"    {char['name']}{faceid_tag} front...", end=" ", flush=True)
        try:
            _generate_image(positive, negative, out_path,
                            width=SD_PORTRAIT_W, height=SD_PORTRAIT_H,
                            face_ref_path=face_ref,
                            pose_image=pose_front if os.path.exists(pose_front) else None)
            _upscale_realesrgan(out_path)
            print("done")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            continue

        # — Three-quarter view (portrait_34.png)
        if not os.path.exists(out_34_path) or force:
            positive_34 = positive.replace(
                "looking at viewer", "three-quarter view, looking slightly away"
            )
            if "looking at viewer" not in positive:
                positive_34 = positive + ", three-quarter view, looking slightly away"
            print(f"    {char['name']}{faceid_tag} ¾ view...", end=" ", flush=True)
            try:
                face_ref_34 = out_path if _check_ipadapter_available() else None
                _generate_image(positive_34, negative, out_34_path,
                                width=SD_PORTRAIT_W, height=SD_PORTRAIT_H,
                                face_ref_path=face_ref_34,
                                pose_image=pose_34 if os.path.exists(pose_34) else None)
                _upscale_realesrgan(out_34_path)
                print("done")
            except RuntimeError as e:
                print(f"FAILED: {e}")


def generate_scene_images(proofread_dir: str, out_dir: str,
                          characters: list | None = None,
                          novel_dir: str = "") -> None:
    """
    Generate one scene image per chapter using the scene extractor + soul link.
    Characters are injected as silhouettes at 0.4 weight for DomoAI composite.
    """
    from images.scene_extractor import extract_scenes, build_scene_prompt

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

        scenes = extract_scenes(text[:4000], chapter_name=ch, novel_dir=novel_dir)
        if scenes:
            positive, negative = build_scene_prompt(scenes[0], characters=characters)
        else:
            positive, negative = scene_image_prompt(text[:500])

        print(f"    {ch}...", end=" ", flush=True)
        try:
            _generate_image(positive, negative, out_path,
                            width=1216, height=832)  # landscape for scenes
            _upscale_realesrgan(out_path)
            print("done")
        except RuntimeError as e:
            print(f"FAILED: {e}")
            continue
