"""
Generates a podcast RSS feed XML file from published episodes.
Output: docs/feed.xml  (hosted on GitHub Pages)

Spotify RSS requirements:
- <enclosure> with mp3 URL, length in bytes, type="audio/mpeg"
- <itunes:duration> in HH:MM:SS
- <itunes:image> with cover art URL
- Valid pubDate in RFC 2822 format
"""

import os
import json
import mutagen
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime

QUEUE_FILE = "podcast/publish_queue.json"
RSS_OUTPUT = "docs/feed.xml"

# Update these in podcast/podcast_config.json after setup
DEFAULT_CONFIG = {
    "podcast_title": "If You Don't Become the Main Character, You'll Die",
    "podcast_description": "AI-narrated audiobook of the top-ranked Korean web novel.",
    "podcast_author": "WebNovel AI Studio",
    "podcast_language": "en-us",
    "cover_art_url": "",          # paste your cover art URL here after uploading it
    "github_pages_url": "",       # e.g. https://yourusername.github.io/my-first-ai-project
}


def _load_config() -> dict:
    config_path = "podcast/podcast_config.json"
    if os.path.exists(config_path):
        with open(config_path) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    # Create default config on first run
    os.makedirs("podcast", exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"  Config created at {config_path} — fill in cover_art_url and github_pages_url!")
    return DEFAULT_CONFIG


def _get_mp3_duration(path: str) -> str:
    """Returns duration as HH:MM:SS string."""
    try:
        audio = mutagen.File(path)
        seconds = int(audio.info.length)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "00:00:00"


def _get_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def generate_rss() -> str:
    """Build RSS XML from published episodes and write to docs/feed.xml."""
    config = _load_config()
    os.makedirs("docs", exist_ok=True)

    state = json.load(open(QUEUE_FILE)) if os.path.exists(QUEUE_FILE) else {"published": []}
    published = sorted(state["published"], key=lambda e: e["episode"])

    # Space episodes 1 day apart going backwards from now
    now = datetime.now(timezone.utc)
    items_xml = ""

    for i, ep in enumerate(reversed(published)):
        pub_date = now - timedelta(days=i)
        audio_url = ep.get("audio_url", "")
        # Use size captured at publish time; fall back to live file if available
        file_size = ep.get("file_size") or _get_file_size(ep.get("path", ""))
        duration = _get_mp3_duration(ep.get("path", ""))

        items_xml += f"""
  <item>
    <title>{_escape(ep['title'])}</title>
    <description>{_escape(ep['title'])}</description>
    <enclosure url="{audio_url}" length="{file_size}" type="audio/mpeg"/>
    <guid isPermaLink="false">{audio_url}</guid>
    <pubDate>{format_datetime(pub_date)}</pubDate>
    <itunes:duration>{duration}</itunes:duration>
    <itunes:episode>{ep['episode']}</itunes:episode>
    <itunes:episodeType>full</itunes:episodeType>
  </item>"""

    feed_url = config["github_pages_url"].rstrip("/") + "/feed.xml"
    cover_url = config["cover_art_url"]

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>{_escape(config['podcast_title'])}</title>
  <description>{_escape(config['podcast_description'])}</description>
  <language>{config['podcast_language']}</language>
  <link>{config['github_pages_url']}</link>
  <atom:link href="{feed_url}" rel="self" type="application/rss+xml"
    xmlns:atom="http://www.w3.org/2005/Atom"/>
  <itunes:author>{_escape(config['podcast_author'])}</itunes:author>
  <itunes:image href="{cover_url}"/>
  <image><url>{cover_url}</url><title>{_escape(config['podcast_title'])}</title></image>
  <itunes:category text="Arts">
    <itunes:category text="Books"/>
  </itunes:category>
  <itunes:explicit>false</itunes:explicit>
  {items_xml}
</channel>
</rss>"""

    with open(RSS_OUTPUT, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"  RSS feed written: {RSS_OUTPUT} ({len(published)} episodes)")
    return RSS_OUTPUT


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
