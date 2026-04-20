"""
Stitches beat/shot clips into full episodes (1 episode per chapter).
Uses Ken Burns pan/zoom fill on character portraits to reach 3-5 min target duration.
Adds crossfade transitions between clips and optional BGM.

Install: pip install moviepy
BGM: Place royalty-free .mp3 at assets/bgm.mp3
"""

from __future__ import annotations
import os
import re
import glob
import tempfile
try:
    # moviepy v1
    from moviepy.editor import (
        VideoFileClip, ImageClip, AudioFileClip, CompositeAudioClip,
        concatenate_videoclips, afx
    )
except ImportError:
    # moviepy v2
    from moviepy import (
        VideoFileClip, ImageClip, AudioFileClip, CompositeAudioClip,
        concatenate_videoclips
    )
    from moviepy import audio as afx

TARGET_MIN_DURATION = 3 * 60   # 3 minutes minimum per episode
TARGET_MAX_DURATION = 5 * 60   # 5 minutes maximum
BGM_VOLUME = 0.10
CROSSFADE = 0.5                # seconds between clips
KEN_BURNS_DURATION = 6         # seconds per Ken Burns fill clip


def _ken_burns_clip(image_path: str, duration: float = KEN_BURNS_DURATION) -> ImageClip:
    """Slow pan/zoom on a portrait image — free visual filler, no API cost."""
    clip = ImageClip(image_path, duration=duration)
    # Gentle zoom: scale from 1.0 to 1.08 over the clip duration
    clip = clip.resize(lambda t: 1 + 0.08 * (t / duration))
    return clip.set_fps(24)


def combine_to_episodes(clips_dir: str, final_dir: str,
                        chars_dir: str = "",
                        bgm_path: str | None = None) -> None:
    """
    Groups beat/shot clips by chapter number, stitches each into an episode.
    Fills gaps to reach TARGET_MIN_DURATION using Ken Burns clips from character portraits.
    Saves to final_dir/episode-NNN.mp4
    """
    os.makedirs(final_dir, exist_ok=True)

    all_clips = sorted(glob.glob(os.path.join(clips_dir, "chapter-*-beat-*-shot-*.mp4")))
    if not all_clips:
        print("  No beat/shot .mp4 files found. Run the compose stage first.")
        return

    # Group by chapter number
    by_chapter: dict[int, list[str]] = {}
    for path in all_clips:
        m = re.search(r'chapter-(\d+)-beat', os.path.basename(path))
        if m:
            ch_num = int(m.group(1))
            by_chapter.setdefault(ch_num, []).append(path)

    # Find a portrait for Ken Burns fill (use protagonist if available)
    fill_portrait = None
    if chars_dir:
        for name in ("protagonist", "leovald", "leonardo"):
            candidate = os.path.join(chars_dir, name, "portrait.png")
            if os.path.exists(candidate):
                fill_portrait = candidate
                break
        if not fill_portrait:
            portraits = glob.glob(os.path.join(chars_dir, "*/portrait.png"))
            if portraits:
                fill_portrait = portraits[0]

    has_bgm = bgm_path is not None and os.path.exists(bgm_path)
    if bgm_path and not has_bgm:
        print(f"  BGM not found at {bgm_path} — continuing without music")

    print(f"  Building {len(by_chapter)} episodes from {len(all_clips)} clips...")

    for ch_num in sorted(by_chapter.keys()):
        out_path = os.path.join(final_dir, f"episode-{ch_num:03d}.mp4")
        if os.path.exists(out_path):
            print(f"  Episode {ch_num:03d} already exists, skipping")
            continue

        clip_files = by_chapter[ch_num]
        print(f"  Building episode-{ch_num:03d} ({len(clip_files)} clips)...", end=" ", flush=True)

        clips = [VideoFileClip(f) for f in clip_files]
        clips_faded = [clips[0]] + [c.crossfadein(CROSSFADE) for c in clips[1:]]
        combined = concatenate_videoclips(clips_faded, padding=-CROSSFADE, method="compose")

        # Ken Burns fill to reach target duration
        if fill_portrait and combined.duration < TARGET_MIN_DURATION:
            fill_clips = []
            fill_needed = TARGET_MIN_DURATION - combined.duration
            while fill_needed > 0:
                dur = min(KEN_BURNS_DURATION, fill_needed)
                fill_clips.append(_ken_burns_clip(fill_portrait, dur))
                fill_needed -= dur
            all_parts = [combined] + fill_clips
            combined = concatenate_videoclips(all_parts, method="compose")

        # Trim to max duration
        if combined.duration > TARGET_MAX_DURATION:
            combined = combined.subclip(0, TARGET_MAX_DURATION)

        # Add BGM
        if has_bgm:
            bgm = AudioFileClip(bgm_path)
            if bgm.duration < combined.duration:
                loops = int(combined.duration / bgm.duration) + 1
                bgm = afx.audio_loop(bgm, nloops=loops)
            bgm = bgm.subclip(0, combined.duration).volumex(BGM_VOLUME)
            audio = CompositeAudioClip([bgm]) if not combined.audio else \
                    CompositeAudioClip([combined.audio, bgm])
            combined = combined.set_audio(audio)

        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            combined.write_videofile(
                out_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=tmp_path,
                remove_temp=True,
                verbose=False,
                logger=None,
            )
        finally:
            for c in clips:
                c.close()
            combined.close()

        duration_min = combined.duration / 60 if hasattr(combined, 'duration') else 0
        print(f"done (~{duration_min:.1f} min)")

    print(f"  Episodes saved to: {final_dir}")
