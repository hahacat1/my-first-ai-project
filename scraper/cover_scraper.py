"""
Generic cover image scraper — works for any novel source URL.
Finds the largest/first prominent image on the page and saves it as cover_source.jpg
Used automatically during the scrape stage for all non-maplesantl scrapers.
"""

from __future__ import annotations
import os
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_cover(source_url: str, novel_dir: str) -> str | None:
    """
    Download the cover image from the novel's source URL.
    Saves to novel_dir/cover_source.{ext}
    Returns saved path or None if not found.
    """
    out_path_base = os.path.join(novel_dir, "cover_source")

    # Skip if already downloaded
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.exists(f"{out_path_base}.{ext}"):
            print(f"  Cover already downloaded: {out_path_base}.{ext}")
            return f"{out_path_base}.{ext}"

    try:
        resp = requests.get(source_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Could not fetch source page for cover: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    img_url = None
    best_area = 0

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src", "")
        if not src or src.startswith("data:"):
            continue

        # Prefer images with explicit large dimensions
        try:
            w = int(img.get("width", 0))
            h = int(img.get("height", 0))
        except (ValueError, TypeError):
            w = h = 0

        area = w * h
        # Skip tiny icons
        if w and w < 80:
            continue
        if h and h < 80:
            continue

        # Pick largest by area, or first if no dimensions given
        if area > best_area or (not img_url and area == 0):
            best_area = area
            img_url = src

    if not img_url:
        print("  No cover image found on source page.")
        return None

    if img_url.startswith("//"):
        img_url = "https:" + img_url
    elif img_url.startswith("/"):
        from urllib.parse import urlparse
        base = urlparse(source_url)
        img_url = f"{base.scheme}://{base.netloc}{img_url}"

    print(f"  Downloading cover: {img_url}")
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        ext = img_url.split(".")[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        out_path = f"{out_path_base}.{ext}"
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"  Cover saved: {out_path}")
        return out_path
    except Exception as e:
        print(f"  Cover download failed: {e}")
        return None
