"""
Stitches video segments + narration audio into full episodes using moviepy.
Adds crossfade transitions between clips and overlays background music if provided.

Install: pip install moviepy
BGM: Download royalty-free music from freepd.com or pixabay.com/music
     Place .mp3 file at assets/bgm.mp3
"""

import os
import glob
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_videoclips, afx
)

BGM_PATH = "assets/bgm.mp3"
BGM_VOLUME = 0.08  # background music much quieter than narration


def combine_to_episodes(segments_dir: str, final_dir: str,
                        segs_per_episode: int = 3) -> None:
    """
    Groups video segments into episodes of ~15 min (3 × 5-min segments by default).
    Adds crossfades between clips. Adds BGM if assets/bgm.mp3 exists.
    Saves final episodes to final_dir/episode-NNN.mp4
    """
    os.makedirs(final_dir, exist_ok=True)

    segment_files = sorted(glob.glob(os.path.join(segments_dir, "seg-*.mp4")))
    if not segment_files:
        print("  No segment .mp4 files found. Run the compose stage first.")
        return

    # Group into episodes
    episodes = [
        segment_files[i:i + segs_per_episode]
        for i in range(0, len(segment_files), segs_per_episode)
    ]

    print(f"  {len(segment_files)} segments → {len(episodes)} episodes")

    has_bgm = os.path.exists(BGM_PATH)
    if has_bgm:
        print(f"  BGM found: {BGM_PATH}")

    for ep_num, ep_files in enumerate(episodes, 1):
        out_path = os.path.join(final_dir, f"episode-{ep_num:03d}.mp4")
        if os.path.exists(out_path):
            print(f"  Episode {ep_num:03d} already exists, skipping")
            continue

        print(f"  Building episode-{ep_num:03d} ({len(ep_files)} segments)...", end=" ", flush=True)

        clips = [VideoFileClip(f) for f in ep_files]

        # Crossfade 1 second between clips
        combined = concatenate_videoclips(clips, method="compose",
                                          padding=-1, transition=None)

        # Add BGM if available — loop it to match video length
        if has_bgm:
            bgm = AudioFileClip(BGM_PATH)
            if bgm.duration < combined.duration:
                loops = int(combined.duration / bgm.duration) + 1
                bgm = afx.audio_loop(bgm, nloops=loops)
            bgm = bgm.subclip(0, combined.duration).volumex(BGM_VOLUME)

            if combined.audio:
                combined = combined.set_audio(
                    CompositeAudioClip([combined.audio, bgm])
                )
            else:
                combined = combined.set_audio(bgm)

        combined.write_videofile(
            out_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=f"/tmp/ep{ep_num}_audio.m4a",
            remove_temp=True,
            verbose=False,
            logger=None,
        )

        for clip in clips:
            clip.close()
        combined.close()

        print("done")

    print(f"  Episodes saved to: {final_dir}")
    print(f"  TIP: Place royalty-free BGM at assets/bgm.mp3 before running this stage.")
