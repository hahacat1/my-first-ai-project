# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Full AI content pipeline for webnovels: scrape → proofread → voice → images → video.
Designed to be reusable across any novel. Currently configured for "If You Don't Become the Main Character, You'll Die" (maplesantl.com).

## Setup
```bash
pip install -r requirements.txt
```
ComfyUI (for images) must be installed separately: https://github.com/comfyanonymous/ComfyUI

## Running the Pipeline
```bash
# Full pipeline
python pipeline/run.py --novel if-you-dont-become-mc --stages all

# Individual stages
python pipeline/run.py --novel if-you-dont-become-mc --stages scrape
python pipeline/run.py --novel if-you-dont-become-mc --stages proofread
python pipeline/run.py --novel if-you-dont-become-mc --stages voice
python pipeline/run.py --novel if-you-dont-become-mc --stages images
python pipeline/run.py --novel if-you-dont-become-mc --stages video
```

## Adding a New Novel
1. Add entry to `pipeline/config.py` NOVELS dict with slug, source_url, scraper name, characters
2. Add a custom scraper to `scraper/sites/<sitename>.py` if the site isn't in lncrawl
3. Run `--stages all`

## Output Structure (per novel)
```
output/<novel-slug>/
  chapters/       ← raw scraped .txt
  proofread/      ← Ollama-cleaned .txt
  voice/          ← chapter-NNN.mp3 (Kokoro TTS)
  images/
    characters/   ← SD portrait per character
    scenes/       ← SD scene image per chapter
    director_prompts.json  ← review/edit before video gen
  video/
    segments/     ← seg-NNN.mp4 (Higgsfield clips)
    final/        ← episode-NNN.mp4 (combined)
  characters.json ← extracted character descriptions
```

## Architecture
- `pipeline/config.py` — novel registry, API keys, model settings
- `pipeline/run.py` — master orchestrator, routes stages
- `scraper/sites/maplesantl.py` — custom scraper for maplesantl.com (300 chapters)
- `scraper/downloader.py` — lncrawl wrapper for all other sites
- `proofreader/proofread.py` — Ollama qwen3.5:9b fixes translation artifacts
- `voice/tts.py` — Kokoro TTS (local, free) → .mp3 per chapter
- `images/character_extractor.py` — Ollama extracts character appearances from text
- `images/sd_generator.py` — ComfyUI REST API (port 8188), uses Anything V5 model
- `images/prompts.py` — builds anime SD prompts; negative prompt blocks 3D/realistic artifacts
- `video/segmenter.py` — splits chapters into ~750-word / ~5-min segments
- `video/director.py` — Ollama writes cinematic Higgsfield prompts; saves to director_prompts.json for review
- `video/composer.py` — Higgsfield API (image-to-video, Kling 3.0 model)
- `video/combiner.py` — moviepy stitches segments into episodes; BGM from assets/bgm.mp3

## Key Config Locations
- Higgsfield API key: `pipeline/config.py` → `HIGGSFIELD_API_KEY`
- Ollama model: `pipeline/config.py` → `OLLAMA_MODEL`
- ComfyUI URL: `pipeline/config.py` → `COMFYUI_URL`
- Segment length: `pipeline/config.py` → `SEGMENT_WORDS` (default 750 = ~5 min)

## Progress & Resuming
All stages save `.progress.json` in their output folder. Re-running any stage skips already-completed files automatically.

## Upgrade Path (when revenue comes)
- Voice: swap Kokoro → ElevenLabs in `voice/tts.py`
- Video: upgrade Higgsfield free → $17/mo plan (600 credits, 16-sec clips)
- Director prompts: add Claude API key for higher quality prompt writing
