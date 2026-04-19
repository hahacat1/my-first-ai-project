"""
Custom scraper for maplesantl.com
Novel: "If You Don't Become the Main Character, You'll Die"
300 episodes, all hosted on maplesantl.com (old maplesan9.wordpress.com URLs redirect here)
"""

import time
import requests
from bs4 import BeautifulSoup

TOC_URL = "https://maplesantl.com/if-you-dont-become-the-main-character-youll-die-list-of-episodes/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Ordered list of CSS selectors to try for the chapter body
CONTENT_SELECTORS = [
    "div.entry-content",
    "div.post-content",
    "div.the-content",
    "article .content",
    "article",
]

# Tags to strip from content (ads, navigation, etc.)
STRIP_TAGS = ["script", "style", "nav", "header", "footer", "figure", "img", "iframe"]


def get_chapter_urls() -> list[dict]:
    """Fetch the table of contents and return a list of {episode, title, url} dicts."""
    print("Fetching table of contents...")
    resp = requests.get(TOC_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all <a> tags inside list items that link to episodes
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "episode" in href.lower() and "episode" in text.lower():
            links.append({"title": text, "url": href})

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for item in links:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    print(f"Found {len(unique)} chapters in table of contents.")
    return unique


def get_chapter_text(url: str) -> str:
    """Fetch a single chapter page and return clean plain text."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Try each selector until we find content
    content_div = None
    for selector in CONTENT_SELECTORS:
        content_div = soup.select_one(selector)
        if content_div:
            break

    if not content_div:
        raise RuntimeError(f"Could not find chapter content on: {url}")

    # Extract paragraphs — skip empty ones and navigation text
    paragraphs = []
    for p in content_div.find_all("p"):
        text = p.get_text(strip=True)
        if text and not _is_navigation(text):
            paragraphs.append(text)

    if not paragraphs:
        # Fallback: grab all text from the content div
        return content_div.get_text(separator="\n").strip()

    return "\n\n".join(paragraphs)


def _is_navigation(text: str) -> bool:
    """Filter out prev/next links and translator notes that aren't story content."""
    nav_phrases = [
        "previous episode", "next episode", "list of episodes",
        "← ", " →", "prev chapter", "next chapter",
        "ko-fi", "novel updates", "patreon",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in nav_phrases)


def scrape_all(output_dir: str, delay: float = 1.0) -> dict:
    """
    Download all chapters to output_dir as chapter-NNN.txt files.
    Returns metadata dict.
    """
    import os
    import json

    chapters = get_chapter_urls()
    os.makedirs(output_dir, exist_ok=True)

    saved = []
    for i, chapter in enumerate(chapters, start=1):
        filename = f"chapter-{i:03d}.txt"
        out_path = os.path.join(output_dir, filename)

        print(f"  [{i}/{len(chapters)}] {chapter['title']}")

        try:
            text = get_chapter_text(chapter["url"])
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"{chapter['title']}\n\n{text}")
            saved.append(out_path)
        except Exception as e:
            print(f"    WARNING: Failed to scrape {chapter['url']}: {e}")

        time.sleep(delay)

    metadata = {
        "title": "If You Don't Become the Main Character, You'll Die",
        "source_url": TOC_URL,
        "chapter_count": len(saved),
        "output_dir": output_dir,
    }
    with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata
