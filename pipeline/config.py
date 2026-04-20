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
        "art_style": (
            "Korean manhwa style, BL romance illustration, beautiful bishonen male characters, "
            "European aristocratic fantasy clothing, noble suits cravats gold trim dark robes, "
            "rich jewel tone color palette deep burgundy midnight blue soft rose gold, "
            "delicate detailed lineart, large expressive eyes, elegant refined poses, "
            "dramatic romantic lighting, opulent interior backgrounds, "
            "official manhwa cover art quality, soft glowing skin, flowing hair"
        ),
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
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct-1m")

# Stable Diffusion (ComfyUI) local API
COMFYUI_URL = "http://127.0.0.1:8188"

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
