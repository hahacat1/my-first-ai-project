"""
Converts video clips to 9:16 vertical format (1080×1920) for YouTube Shorts and TikTok.
Adds a title card overlay (episode + part number) and optional BGM.
"""

from __future__ import annotations
import os
import tempfile

try:
    from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, AudioFileClip, afx
except ImportError:
    from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, AudioFileClip
    from moviepy import audio as afx

TARGET_W = 1080
TARGET_H = 1920
BGM_VOLUME = 0.10


def to_vertical(clip):
    """
    Center-crop a clip to 9:16 (1080×1920).
    If the clip is taller than 9:16, letterbox the sides.
    If wider, crop the top/bottom.
    """
    src_w, src_h = clip.size
    target_ratio = TARGET_W / TARGET_H
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # Wider than 9:16 — crop left/right
        new_w = int(src_h * target_ratio)
        x1 = (src_w - new_w) // 2
        clip = clip.crop(x1=x1, x2=x1 + new_w)
    elif src_ratio < target_ratio:
        # Taller than 9:16 — crop top/bottom (keep center)
        new_h = int(src_w / target_ratio)
        y1 = (src_h - new_h) // 2
        clip = clip.crop(y1=y1, y2=y1 + new_h)

    return clip.resize((TARGET_W, TARGET_H))


def add_title_card(clip, title: str):
    """
    Overlay a semi-transparent bar at the top with the episode/part title.
    White text, centered horizontally.
    """
    bar_h = 110
    bar = ColorClip(size=(TARGET_W, bar_h), color=(0, 0, 0), duration=clip.duration)
    bar = bar.set_opacity(0.55).set_position(("center", 0))

    try:
        txt = TextClip(
            title,
            fontsize=52,
            color="white",
            font="Arial-Bold",
            size=(TARGET_W - 60, None),
            method="caption",
        ).set_duration(clip.duration).set_position(("center", 25))
        return CompositeVideoClip([clip, bar, txt])
    except Exception:
        # TextClip requires ImageMagick; if not available, skip text overlay
        return CompositeVideoClip([clip, bar])


def make_short(clip_paths: list[str], out_path: str, title: str,
               bgm_path: str | None = None) -> None:
    """
    Stitch clips, convert to 9:16, add title card and optional BGM.
    Saves to out_path as H.264 MP4.
    """
    from moviepy.editor import concatenate_videoclips  # type: ignore

    clips = [VideoFileClip(p) for p in clip_paths]
    combined = concatenate_videoclips(clips, method="compose")

    vertical = to_vertical(combined)
    titled = add_title_card(vertical, title)

    if bgm_path and os.path.exists(bgm_path):
        bgm = AudioFileClip(bgm_path)
        if bgm.duration < titled.duration:
            loops = int(titled.duration / bgm.duration) + 1
            try:
                bgm = afx.audio_loop(bgm, nloops=loops)
            except AttributeError:
                from moviepy.audio.fx.audio_loop import audio_loop
                bgm = audio_loop(bgm, nloops=loops)
        bgm = bgm.subclip(0, titled.duration).volumex(BGM_VOLUME)
        titled = titled.set_audio(bgm)

    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        titled.write_videofile(
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
