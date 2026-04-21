"""
Per-novel configuration. Add a new entry here for each novel you want to process.
API keys are loaded from .env (copy .env.example → .env and fill in).
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; keys can also be set in the environment directly

NOVELS = {
    "if-you-dont-become-the-main-character-youll-die": {
        "title": "If You Don't Become the Main Character, You'll Die",
        "source_url": "https://maplesantl.com/if-you-dont-become-the-main-character-youll-die-list-of-episodes/",
        "scraper": "maplesantl",
        "slug": "if-you-dont-become-the-main-character-youll-die",
        # Target audience & visual tone — shapes ComfyUI prompts
        "audience": "female (BL romance)",
        "art_style": "masterpiece, best quality, Korean manhwa, BL romance, elegant bishonen aesthetic, rich jewel tones, delicate lineart",
        # Key characters for portrait generation — add more as you read the novel
        "characters": [
            {
                "name": "Protagonist",
                "description": "young Korean man, early 20s, dark hair, average build, ordinary looking, surprised expression",
            },
        ],
    },
}

# LM Studio model/URL — used for proofreading, title enrichment, and director prompts
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen3.5-9b")

# Stable Diffusion (ComfyUI) local API
COMFYUI_URL = "http://127.0.0.1:8188"

# ComfyUI image generation settings
# Checkpoint: AnimagineXL 4.0 (SDXL) — best free anime model
SD_CHECKPOINT = os.getenv("SD_CHECKPOINT", "animagine-xl-4.0.safetensors")
# VAE: SDXL native VAE for AnimagineXL
SD_VAE = os.getenv("SD_VAE", "sdxl_vae.safetensors")
# Sampler: DPM++ 2M Karras — sharper, more detailed than euler_ancestral for SDXL
SD_SAMPLER = os.getenv("SD_SAMPLER", "dpmpp_2m")
SD_SCHEDULER = os.getenv("SD_SCHEDULER", "karras")
SD_STEPS = int(os.getenv("SD_STEPS", "35"))
SD_CFG = float(os.getenv("SD_CFG", "7.0"))
# Portrait resolution — 896x1152 is SDXL native aspect ratio for portraits
SD_PORTRAIT_W = int(os.getenv("SD_PORTRAIT_W", "896"))
SD_PORTRAIT_H = int(os.getenv("SD_PORTRAIT_H", "1152"))
# Hires fix: upscale factor applied after base generation (1.0 = disabled)
SD_HIRES_SCALE = float(os.getenv("SD_HIRES_SCALE", "1.5"))
SD_HIRES_DENOISE = float(os.getenv("SD_HIRES_DENOISE", "0.5"))
SD_HIRES_STEPS = int(os.getenv("SD_HIRES_STEPS", "20"))
# IP-Adapter FaceID — SDXL version for AnimagineXL
SD_IPADAPTER_MODEL = os.getenv("SD_IPADAPTER_MODEL", "ip-adapter-faceid-plusv2_sdxl.bin")
SD_FACE_WEIGHT = float(os.getenv("SD_FACE_WEIGHT", "0.80"))
# ControlNet OpenPose — pose consistency across front/¾ portraits
SD_CONTROLNET_MODEL = os.getenv("SD_CONTROLNET_MODEL", "OpenPoseXL2.safetensors")
SD_CONTROLNET_STRENGTH = float(os.getenv("SD_CONTROLNET_STRENGTH", "0.6"))
# Real-ESRGAN upscale binary path (leave empty to skip post-processing upscale)
REALESRGAN_BIN = os.getenv("REALESRGAN_BIN", os.path.expanduser("~/bin/realesrgan-ncnn-vulkan"))

# Higgsfield API — set in .env as HIGGSFIELD_API_KEY=your_key_here
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "")

# Higgsfield video model — seedream-5.0-lite (free), seedance-2.0 (paid, higher quality)
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "seedream-5.0-lite")

# Words per minute for narration (used to calculate 5-min segment length)
NARRATION_WPM = 150
SEGMENT_WORDS = NARRATION_WPM * 5  # ~750 words per 5-min clip

# Publish stage — how many items to upload per run (avoid quota exhaustion)
PUBLISH_FULL_PER_RUN = int(os.getenv("PUBLISH_FULL_PER_RUN", "1"))
PUBLISH_SHORTS_PER_RUN = int(os.getenv("PUBLISH_SHORTS_PER_RUN", "2"))
