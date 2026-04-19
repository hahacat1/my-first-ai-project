import subprocess
import sys
import os
import json


def download_novel(url: str, output_dir: str) -> dict:
    """
    Uses lightnovel-crawler (lncrawl) to download all chapters from a novel URL.
    Returns metadata dict with title, source, and list of downloaded chapter files.
    """
    novel_output = os.path.join(output_dir, "_raw")
    os.makedirs(novel_output, exist_ok=True)

    cmd = [
        sys.executable, "-m", "lncrawl",
        "--source", url,
        "--output", novel_output,
        "--format", "text",
        "--all",
        "--suppress",
    ]

    print(f"Downloading from: {url}")
    print("This may take a few minutes depending on how many chapters there are...\n")

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"lncrawl failed. Make sure the URL is correct and the site is supported.\n"
            f"Run: lncrawl --list-sources   to see all supported sites."
        )

    # Find the novel folder lncrawl created inside _raw
    subdirs = [d for d in os.listdir(novel_output) if os.path.isdir(os.path.join(novel_output, d))]
    if not subdirs:
        raise RuntimeError("Download completed but no output folder was found. Check the URL.")

    novel_folder = os.path.join(novel_output, subdirs[0])

    # Collect all text files lncrawl produced
    text_dir = os.path.join(novel_folder, "text")
    if not os.path.isdir(text_dir):
        # Some versions output directly in the novel folder
        text_dir = novel_folder

    chapter_files = sorted([
        os.path.join(text_dir, f)
        for f in os.listdir(text_dir)
        if f.endswith(".txt")
    ])

    return {
        "title": subdirs[0],
        "source_url": url,
        "raw_folder": novel_folder,
        "chapter_files": chapter_files,
        "chapter_count": len(chapter_files),
    }
