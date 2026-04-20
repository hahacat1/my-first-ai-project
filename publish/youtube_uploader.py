"""
YouTube Data API v3 uploader for full episodes and Shorts.

One-time setup:
1. Google Cloud Console → enable YouTube Data API v3
2. Create OAuth2 credentials (Desktop app) → download client_secrets.json
3. Place client_secrets.json in the project root
4. First run will open a browser window for Google login → token saved automatically

After setup, uploads are fully automated.
"""

from __future__ import annotations
import os
import json

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = os.path.expanduser("~/.config/webnovel/youtube_token.json")
CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json")

CATEGORY_ENTERTAINMENT = "24"
NOVEL_TAGS = ["webnovel", "manhwa", "BL", "anime", "lightnovel", "webtoon", "koreannovel"]


def _get_credentials():
    """Load or refresh OAuth2 credentials, opening browser on first run."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS):
                raise FileNotFoundError(
                    f"YouTube client_secrets.json not found at '{CLIENT_SECRETS}'.\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def _build_client():
    if not YOUTUBE_AVAILABLE:
        raise ImportError(
            "YouTube client not installed. Run:\n"
            "  pip install google-api-python-client google-auth-oauthlib"
        )
    return build("youtube", "v3", credentials=_get_credentials())


def upload_episode(video_path: str, title: str, description: str,
                   tags: list[str] | None = None) -> str:
    """
    Upload a full episode to YouTube as a regular video.
    Returns the YouTube video ID.
    """
    youtube = _build_client()
    tags = (tags or []) + NOVEL_TAGS

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ENTERTAINMENT,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"    Uploading to YouTube: {os.path.basename(video_path)}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"    Upload progress: {int(status.progress() * 100)}%", end="\r")

    video_id = response["id"]
    print(f"    Uploaded: https://youtube.com/watch?v={video_id}")
    return video_id


def upload_short(video_path: str, title: str, description: str,
                 tags: list[str] | None = None) -> str:
    """
    Upload a 30-40 sec clip as a YouTube Short.
    Title must contain #Shorts for YouTube to classify it correctly.
    Returns the YouTube video ID.
    """
    short_title = f"{title} #Shorts"[:100]
    short_desc = f"{description}\n\n#Shorts #Anime #WebNovel #Manhwa"
    return upload_episode(video_path, short_title, short_desc, tags)
