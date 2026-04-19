"""
Per-novel configuration. Add a new entry here for each novel you want to process.
"""

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

# Ollama model used for proofreading and director prompts
OLLAMA_MODEL = "qwen3.5:9b"

# Stable Diffusion (ComfyUI) local API
COMFYUI_URL = "http://127.0.0.1:8188"

# Higgsfield API — set your key here when you sign up
HIGGSFIELD_API_KEY = ""  # get from higgsfield.ai

# Words per minute for narration (used to calculate 5-min segment length)
NARRATION_WPM = 150
SEGMENT_WORDS = NARRATION_WPM * 5  # ~750 words per 5-min clip
