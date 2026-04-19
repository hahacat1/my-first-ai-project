"""
Stitches video segments + narration audio into full episodes using moviepy.
Adds crossfade transitions between clips and overlays background music if provided.

Install: pip install moviepy
BGM: Download royalty-free music from freepd.com or pixabay.com/music
     Place .mp3 file at assets/bgm.mp3
"""

import os
import glob
import tempfile
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, afx
)

BGM_VOLUME = 0.08  # background music much quieter than narration


def combine_to_episodes(segments_dir: str, final_dir: str,
                        segs_per_episode: int = 3,
                        bgm_path: str | None = None) -> None:
    """
    Groups video segments into episodes of ~15 min (3 × 5-min segments by default).
    Adds 1-second crossfades between clips.
    Overlays BGM if bgm_path is provided and the file exists.
    Saves final episodes to final_dir/episode-NNN.mp4
    """
    os.makedirs(final_dir, exist_ok=True)

    segment_files = sorted(glob.glob(os.path.join(segments_dir, "seg-*.mp4")))
    if not segment_files:
        print("  No segment .mp4 files found. Run the compose stage first.")
        return

    episodes = [
        segment_files[i:i + segs_per_episode]
        for i in range(0, len(segment_files), segs_per_episode)
    ]

    print(f"  {len(segment_files)} segments → {len(episodes)} episodes")

    has_bgm = bgm_path is not None and os.path.exists(bgm_path)
    if bgm_path and not has_bgm:
        print(f"  BGM not found at {bgm_path} — continuing without music")
    elif has_bgm:
        print(f"  BGM: {bgm_path}")

    for ep_num, ep_files in enumerate(episodes, 1):
        out_path = os.path.join(final_dir, f"episode-{ep_num:03d}.mp4")
        if os.path.exists(out_path):
            print(f"  Episode {ep_num:03d} already exists, skipping")
            continue

        print(f"  Building episode-{ep_num:03d} ({len(ep_files)} segments)...", end=" ", flush=True)

        clips = [VideoFileClip(f) for f in ep_files]

        # Proper 1-second crossfade: apply crossfadein to every clip after the first
        clips_faded = [clips[0]] + [c.crossfadein(1) for c in clips[1:]]
        combined = concatenate_videoclips(clips_faded, padding=-1, method="compose")

        if has_bgm:
            bgm = AudioFileClip(bgm_path)
            if bgm.duration < combined.duration:
                loops = int(combined.duration / bgm.duration) + 1
                bgm = afx.audio_loop(bgm, nloops=loops)
            bgm = bgm.subclip(0, combined.duration).volumex(BGM_VOLUME)
            if combined.audio:
                combined = combined.set_audio(CompositeAudioClip([combined.audio, bgm]))
            else:
                combined = combined.set_audio(bgm)

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
            for clip in clips:
                clip.close()
            combined.close()

        print("done")

    print(f"  Episodes saved to: {final_dir}")
    if not has_bgm:
        print(f"  TIP: Pass bgm_path='assets/bgm.mp3' to add background music.")
