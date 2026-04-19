"""
Calls Higgsfield API to convert scene images + director prompts into video clips.

Setup:
1. Sign up at higgsfield.ai (free tier = 10 clips/day)
2. Get your API key from the dashboard
3. Set HIGGSFIELD_API_KEY in pipeline/config.py

Free tier limits: 8-second clips, 10/day
Paid ($17/mo): 16-second clips, 600 credits/month
"""

import os
import time
import json
import requests
from pipeline.config import HIGGSFIELD_API_KEY

HIGGSFIELD_API = "https://api.higgsfield.ai/v1"


def _get_headers() -> dict:
    if not HIGGSFIELD_API_KEY:
        raise RuntimeError(
            "Higgsfield API key not set.\n"
            "1. Sign up at https://higgsfield.ai\n"
            "2. Copy your API key\n"
            "3. Set HIGGSFIELD_API_KEY in pipeline/config.py"
        )
    return {"Authorization": f"Bearer {HIGGSFIELD_API_KEY}", "Content-Type": "application/json"}


def _image_to_video(image_path: str, prompt: str, duration: int = 6) -> bytes:
    """Submit an image-to-video job and return the video bytes when done."""
    headers = _get_headers()

    # Upload image first
    with open(image_path, "rb") as f:
        img_resp = requests.post(
            f"{HIGGSFIELD_API}/upload",
            headers={"Authorization": f"Bearer {HIGGSFIELD_API_KEY}"},
            files={"file": f},
            timeout=60,
        )
    img_resp.raise_for_status()
    image_url = img_resp.json()["url"]

    # Submit generation job
    job_resp = requests.post(
        f"{HIGGSFIELD_API}/video/generate",
        headers=headers,
        json={
            "prompt": prompt,
            "image_url": image_url,
            "duration": duration,
            "model": "kling-3.0",  # best quality on Higgsfield
        },
        timeout=30,
    )
    job_resp.raise_for_status()
    job_id = job_resp.json()["id"]

    # Poll until done (usually 1-3 minutes)
    for _ in range(180):
        time.sleep(5)
        status_resp = requests.get(
            f"{HIGGSFIELD_API}/video/{job_id}",
            headers=headers,
            timeout=15,
        )
        data = status_resp.json()
        status = data.get("status")

        if status == "completed":
            video_url = data["output_url"]
            video_resp = requests.get(video_url, timeout=120)
            return video_resp.content
        elif status == "failed":
            raise RuntimeError(f"Higgsfield job failed: {data.get('error', 'unknown')}")

    raise RuntimeError(f"Higgsfield job timed out: {job_id}")


def compose_segments(segments: list[dict], scenes_dir: str,
                     voice_dir: str, out_dir: str) -> None:
    """
    For each segment: find scene image + director prompt → generate video clip.
    Saves to out_dir/seg-NNN.mp4
    """
    os.makedirs(out_dir, exist_ok=True)

    progress_file = os.path.join(out_dir, ".progress.json")
    done = set(json.load(open(progress_file)) if os.path.exists(progress_file) else [])

    print(f"  Generating {len(segments)} video clips via Higgsfield...")

    for i, seg in enumerate(segments, 1):
        out_filename = f"{seg['id']}.mp4"
        if out_filename in done:
            print(f"  [{i}/{len(segments)}] {seg['id']} already done")
            continue

        # Find scene image — use first chapter's image for this segment
        first_chapter = seg["chapters"][0].replace(".txt", ".png")
        image_path = os.path.join(scenes_dir, first_chapter)
        if not os.path.exists(image_path):
            print(f"  [{i}/{len(segments)}] {seg['id']} — no scene image found, skipping")
            continue

        director_prompt = seg.get("director_prompt", "anime scene, cinematic, 4K, fluid motion")
        out_path = os.path.join(out_dir, out_filename)

        print(f"  [{i}/{len(segments)}] {seg['id']}...", end=" ", flush=True)
        try:
            video_bytes = _image_to_video(image_path, director_prompt)
            with open(out_path, "wb") as f:
                f.write(video_bytes)
            print(f"done ({len(video_bytes) // 1024} KB)")
            done.add(out_filename)
            with open(progress_file, "w") as f:
                json.dump(list(done), f)
        except RuntimeError as e:
            print(f"FAILED: {e}")
            if "API key" in str(e):
                break  # no point continuing without a key
