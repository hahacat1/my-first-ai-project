"""
Higgsfield SoulID manager — creates persistent character identities from portrait images.
Soul IDs are cached in novels/<slug>/soul_ids.json and reused across all sessions.

Cost: $3 per Soul creation. Only key characters (protagonist/antagonist) get Souls.
Fallback: if no Soul exists, composer uses portrait.png directly.
"""

from __future__ import annotations
import json
import os
import time
import requests
from pipeline.config import HIGGSFIELD_API_KEY

HIGGSFIELD_API = "https://api.higgsfield.ai/v1"
SOUL_REFERENCE_STRENGTH = 0.85  # 0.0–1.0; higher = more faithful to portrait
KEY_ROLES = {"protagonist", "antagonist"}


def _headers() -> dict:
    return {"Authorization": f"Bearer {HIGGSFIELD_API_KEY}"}


def load_souls(novel_dir: str) -> dict:
    """Return {name_slug: soul_id} from soul_ids.json, or empty dict."""
    path = os.path.join(novel_dir, "soul_ids.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_souls(novel_dir: str, souls: dict) -> None:
    path = os.path.join(novel_dir, "soul_ids.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(souls, f, indent=2)


def _upload_image(image_path: str) -> str:
    """Upload portrait to Higgsfield and return the hosted URL."""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{HIGGSFIELD_API}/upload",
            headers=_headers(),
            files={"file": f},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["url"]


def _create_soul(name: str, portrait_path: str) -> str:
    """Upload portrait → create Soul → return soul_id. Takes ~3-5 minutes."""
    print(f"    Uploading portrait for {name}...", end=" ", flush=True)
    image_url = _upload_image(portrait_path)
    print("uploaded.")

    print(f"    Creating Soul for {name} (this takes ~3-5 min)...", end=" ", flush=True)
    resp = requests.post(
        f"{HIGGSFIELD_API}/soul/create",
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "name": name,
            "input_images": [{"type": "image_url", "image_url": image_url}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    soul_id = data.get("id") or data.get("soul_id")

    # Poll until training completes
    for _ in range(60):
        time.sleep(5)
        status_resp = requests.get(
            f"{HIGGSFIELD_API}/soul/{soul_id}",
            headers=_headers(),
            timeout=15,
        )
        status = status_resp.json().get("status", "")
        if status == "completed":
            print("done.")
            return soul_id
        elif status == "failed":
            raise RuntimeError(f"Soul creation failed for {name}")

    raise RuntimeError(f"Soul creation timed out for {name}")


def soul_to_keyframe(soul_id: str, prompt: str) -> bytes:
    """
    Generate a scene-appropriate keyframe image using the Soul's character identity.
    Returns PNG bytes. Called per shot before image-to-video.
    """
    resp = requests.post(
        f"{HIGGSFIELD_API}/text2image/soul",
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "custom_reference_id": soul_id,
            "custom_reference_strength": SOUL_REFERENCE_STRENGTH,
            "width": 832,
            "height": 1216,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Poll if async
    job_id = data.get("id")
    if job_id:
        for _ in range(60):
            time.sleep(3)
            poll = requests.get(f"{HIGGSFIELD_API}/image/{job_id}", headers=_headers(), timeout=15).json()
            if poll.get("status") == "completed":
                img_url = poll["output_url"]
                return requests.get(img_url, timeout=60).content
            elif poll.get("status") == "failed":
                raise RuntimeError(f"Soul keyframe generation failed")
        raise RuntimeError("Soul keyframe timed out")

    # Synchronous response
    img_url = data.get("output_url") or data.get("url")
    if img_url:
        return requests.get(img_url, timeout=60).content

    raise RuntimeError(f"Unexpected Soul keyframe response: {data}")


def ensure_souls(characters: list[dict], chars_dir: str, novel_dir: str) -> dict:
    """
    Create Souls for key characters (protagonist/antagonist) that don't have one yet.
    Returns updated {name_slug: soul_id} dict.
    """
    if not HIGGSFIELD_API_KEY:
        print("  [SOUL] No Higgsfield API key — skipping Soul creation, will use portraits directly.")
        return {}

    souls = load_souls(novel_dir)
    created = 0

    for char in characters:
        role = char.get("role", "").lower()
        if not any(r in role for r in KEY_ROLES):
            continue

        name_slug = char["name"].lower().replace(" ", "_").replace("/", "_")
        if name_slug in souls:
            print(f"  [SOUL] {char['name']} — already registered (id: {souls[name_slug][:12]}...)")
            continue

        portrait_path = os.path.join(chars_dir, name_slug, "portrait.png")
        if not os.path.exists(portrait_path):
            print(f"  [SOUL] {char['name']} — no portrait found, skipping")
            continue

        print(f"  [SOUL] Registering {char['name']} (${3} one-time cost)...")
        try:
            soul_id = _create_soul(char["name"], portrait_path)
            souls[name_slug] = soul_id
            _save_souls(novel_dir, souls)
            created += 1
        except Exception as e:
            print(f"  [SOUL] Failed to create Soul for {char['name']}: {e}")

    if created:
        print(f"  [SOUL] Created {created} new Soul(s). Cached in {novel_dir}/soul_ids.json")
    else:
        print(f"  [SOUL] {len(souls)} Soul(s) already registered, none to create.")

    return souls
