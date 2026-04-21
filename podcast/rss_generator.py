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

RSS_OUTPUT = "docs/feed.xml"

DEFAULT_CONFIG = {
    "podcast_title": "If You Don't Become the Main Character, You'll Die",
    "podcast_description": "AI-narrated audiobook of the top-ranked Korean web novel.",
    "podcast_author": "WebNovel AI Studio",
    "podcast_language": "en-us",
    "cover_art_url": "",
    "github_pages_url": "",
}


def _config_path(novel_dir: str) -> str:
    return os.path.join(novel_dir, "podcast", "podcast_config.json")


def _queue_path(novel_dir: str) -> str:
    return os.path.join(novel_dir, "podcast", "publish_queue.json")


def _load_config(novel_dir: str) -> dict:
    path = _config_path(novel_dir)
    if os.path.exists(path):
        with open(path) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"  Config created at {path} — fill in cover_art_url and github_pages_url!")
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


def generate_rss(novel_dir: str) -> str:
    """Build RSS XML from published episodes and write to docs/feed.xml."""
    config = _load_config(novel_dir)
    os.makedirs("docs", exist_ok=True)

    queue_file = _queue_path(novel_dir)
    state = json.load(open(queue_file)) if os.path.exists(queue_file) else {"published": []}
    published = sorted(state["published"], key=lambda e: e["episode"])

    now = datetime.now(timezone.utc)
    items_xml = ""

    for i, ep in enumerate(reversed(published)):
        pub_date_str = ep.get("published_at", "")
        if pub_date_str:
            pub_date = datetime.fromisoformat(pub_date_str)
        else:
            pub_date = now - timedelta(days=i)
        audio_url = ep.get("audio_url", "")
        file_size = ep.get("file_size") or _get_file_size(ep.get("path", ""))
        duration = _get_mp3_duration(ep.get("path", ""))
        # Use generated synopsis if available, else fall back to title
        ep_title = ep["title"].split(" — ", 1)[-1] if " — " in ep["title"] else ep["title"]
        description = _escape(ep.get("synopsis") or ep_title)

        items_xml += f"""
  <item>
    <title>{_escape(ep_title)}</title>
    <description>{description}</description>
    <itunes:summary>{description}</itunes:summary>
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
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>{_escape(config['podcast_title'])}</title>
  <description>{_escape(config['podcast_description'])}</description>
  <language>{config['podcast_language']}</language>
  <link>{config['github_pages_url']}</link>
  <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>
  <itunes:author>{_escape(config['podcast_author'])}</itunes:author>
  <itunes:owner>
    <itunes:name>{_escape(config['podcast_author'])}</itunes:name>
    <itunes:email>{config.get('podcast_email', '')}</itunes:email>
  </itunes:owner>
  <itunes:image href="{cover_url}"/>
  <image><url>{cover_url}</url><title>{_escape(config['podcast_title'])}</title></image>
  <itunes:category text="Arts">
    <itunes:category text="Books"/>
  </itunes:category>
  <itunes:subtitle>{_escape(config.get('podcast_subtitle', ''))}</itunes:subtitle>
  <itunes:keywords>{_escape(config.get('podcast_keywords', ''))}</itunes:keywords>
  <itunes:explicit>false</itunes:explicit>
  <itunes:type>episodic</itunes:type>
  {items_xml}
</channel>
</rss>"""

    with open(RSS_OUTPUT, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"  RSS feed written: {RSS_OUTPUT} ({len(published)} episodes)")
    return RSS_OUTPUT


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
