"""
TikTok Content Posting API v2 uploader.

Setup (one-time, requires TikTok developer approval):
1. Apply at https://developers.tiktok.com for Content Posting API access
2. Create an app → get CLIENT_KEY and CLIENT_SECRET
3. Complete OAuth2 flow to get ACCESS_TOKEN
4. Add to .env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN

TikTok API approval can take 1-7 days.
"""

from __future__ import annotations
import os
import math
import requests

TIKTOK_API = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB per chunk

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

NOVEL_HASHTAGS = "#webnovel #manhwa #BL #anime #lightnovel #webtoon #koreannovel"


def _headers() -> dict:
    if not ACCESS_TOKEN:
        raise RuntimeError(
            "TikTok access token not set.\n"
            "Set TIKTOK_ACCESS_TOKEN in .env after completing OAuth2 flow.\n"
            "Apply for API access at: https://developers.tiktok.com"
        )
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=UTF-8",
    }


def upload_video(video_path: str, title: str, description: str = "") -> str:
    """
    Upload a video to TikTok using Direct Post (published immediately).
    Returns the TikTok publish_id.
    """
    file_size = os.path.getsize(video_path)
    chunk_count = math.ceil(file_size / CHUNK_SIZE)

    caption = f"{title}\n{description}\n{NOVEL_HASHTAGS}"[:2200]

    # Step 1: Initialize upload
    init_resp = requests.post(
        f"{TIKTOK_API}/post/publish/video/init/",
        headers=_headers(),
        json={
            "post_info": {
                "title": caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": CHUNK_SIZE,
                "total_chunk_count": chunk_count,
            },
        },
        timeout=30,
    )
    init_resp.raise_for_status()
    data = init_resp.json()["data"]
    publish_id = data["publish_id"]
    upload_url = data["upload_url"]

    # Step 2: Upload chunks
    print(f"    Uploading to TikTok: {os.path.basename(video_path)} ({chunk_count} chunk(s))")
    with open(video_path, "rb") as f:
        for chunk_idx in range(chunk_count):
            chunk_data = f.read(CHUNK_SIZE)
            start = chunk_idx * CHUNK_SIZE
            end = start + len(chunk_data) - 1

            resp = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk_data)),
                    "Content-Type": "video/mp4",
                },
                data=chunk_data,
                timeout=120,
            )
            resp.raise_for_status()
            print(f"    Chunk {chunk_idx + 1}/{chunk_count} uploaded")

    print(f"    TikTok publish_id: {publish_id}")
    return publish_id
