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
    "if-you-dont-become-mc": {
        "title": "If You Don't Become the Main Character, You'll Die",
        "source_url": "https://maplesantl.com/if-you-dont-become-the-main-character-youll-die-list-of-episodes/",
        "scraper": "maplesantl",
        "slug": "if-you-dont-become-mc",
        # Key characters for portrait generation — add more as you read the novel
        "characters": [
            {
                "name": "Protagonist",
                "description": "young Korean man, early 20s, dark hair, average build, ordinary looking, surprised expression",
            },
        ],
    },
}

# Ollama model used for character extraction and director prompts
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

# LM Studio model/URL used for proofreading and title enrichment
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "google/gemma-4-e4b")

# Stable Diffusion (ComfyUI) local API
COMFYUI_URL = "http://127.0.0.1:8188"

# Higgsfield API — set in .env as HIGGSFIELD_API_KEY=your_key_here
HIGGSFIELD_API_KEY = os.getenv("HIGGSFIELD_API_KEY", "")

# Words per minute for narration (used to calculate 5-min segment length)
NARRATION_WPM = 150
SEGMENT_WORDS = NARRATION_WPM * 5  # ~750 words per 5-min clip
