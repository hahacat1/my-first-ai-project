"""
Uploads mp3 files to Archive.org (free, unlimited storage).

Setup (one-time):
1. Create a free account at archive.org
2. Run: pip install internetarchive
3. Run: ia configure   (enter your archive.org email + password)
   This saves credentials to ~/.config/internetarchive/ia.ini

Each novel gets its own Archive.org item (like a folder).
Audio files are publicly accessible via a direct URL.
"""

import os


def _get_ia():
    try:
        import internetarchive as ia
        return ia
    except ImportError:
        raise ImportError(
            "internetarchive not installed. Run:\n"
            "  pip install internetarchive\n"
            "  ia configure"
        )


def _item_identifier(novel_slug: str) -> str:
    """Archive.org item ID — must be globally unique, lowercase, no spaces."""
    return f"webnovel-{novel_slug}-audiobook"


def upload_episodes(episodes: list[dict], novel_slug: str, novel_title: str) -> dict:
    """
    Upload a batch of episode mp3s to Archive.org.
    Returns dict of {filename: public_url}
    """
    ia = _get_ia()
    identifier = _item_identifier(novel_slug)
    metadata = {
        "title": f"{novel_title} — Audiobook",
        "mediatype": "audio",
        "subject": ["audiobook", "webnovel", "podcast"],
        "description": f"AI-narrated audiobook of {novel_title}",
    }

    urls = {}
    for ep in episodes:
        path = ep["path"]
        filename = ep["file"]
        print(f"  Uploading {filename} to Archive.org...", end=" ", flush=True)
        try:
            ia.upload(identifier, files={filename: path}, metadata=metadata, checksum=True)
            public_url = f"https://archive.org/download/{identifier}/{filename.replace(' ', '%20')}"
            urls[filename] = public_url
            print("done")
        except Exception as e:
            print(f"FAILED: {e}")

    return urls
