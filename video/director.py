"""
Uses LM Studio to write storyboard-style director prompts for each chapter.
Each shot prompt = ~10-15 seconds of video. Target ~12-18 shots per chapter (~3 min).
The model decides how many beats and shots the chapter naturally needs.
Output: director_prompts/chapter-NNN.json (review/edit before video generation).
"""

from __future__ import annotations
import os
import json
import re
from openai import OpenAI
from pipeline.config import LM_STUDIO_URL, LM_STUDIO_MODEL

_client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

DIRECTOR_SYSTEM_TEMPLATE = """You are a cinematic anime director writing AI video prompts for a Korean web novel adaptation.

Read the chapter and:
1. Write a 3-4 sentence SYNOPSIS of the episode's story arc and emotional tone.
2. Break the chapter into dramatic beats — scene shifts, emotional changes, dialogue moments, action sequences.
3. For each beat write 2-4 shot prompts. Each shot = ~8 seconds of video. Aim for 12-18 shots total per episode.

You are designing a sequence, not isolated prompts. Each shot must build on the last — advancing the emotion, changing the angle, introducing new visual information. Never repeat a framing, lighting setup, or action across consecutive shots.

Shot types to rotate across the episode:
- Wide establishing (isolation, scale, loneliness)
- Medium (emotion, performance, character reaction)
- Close-up (intensity, a single detail, a face or hand)
- Cutaway (symbolic object, environment, reaction that carries subtext)
- Static locked shot (use deliberately for high-emotion moments — stillness is powerful)

RULES FOR EVERY SHOT PROMPT:

RULE 1 — FORMAT
One continuous prose sentence. No brackets. No slashes. No lists. No pipe characters.

RULE 2 — WORD ORDER (controls AI weight)
style tags → character appearance → single action → environment → camera → lighting → mood → motion

RULE 3 — STYLE TAGS
6-8 words max. Use: ({ART_STYLE})

RULE 4 — CHARACTER APPEARANCE
Never write "the protagonist" or a bare name. Always give hair color, length, age feel, and one expression marker.
On the first shot of each beat, use the full descriptor. On subsequent shots in the same beat, a short reference ("he", "his hands", "Leonardo") is enough — don't repeat the full description every shot.
Wrong: "the protagonist reads a document"
Right first shot: "a young man with soft black hair and tired eyes, wearing a loose shirt"
Right subsequent shot: "he lowers the page slowly, breath just visible"

RULE 5 — ONE ACTION PER SHOT, WITH MICRO-DETAIL
One primary action, one secondary physical detail. The AI renders 8 seconds — give it one thing to commit to.
Wrong: "lowering the pages, staring at his hands, trembling" — three things competing
Right: "slowly lowering the pages, his fingers hovering mid-air as something stops him"

Make the action specific enough to reveal character. Generic actions flatten scenes; specific hesitations reveal them.
Wrong: "examining the wound" — generic, no inner life
Right: "his hand pausing just before touching the bruise, hovering an inch away" — hesitation = character
Wrong: "looking at the document" — static
Right: "his eyes scanning the page, stopping at one line, not moving past it" — specific = cinematic

Characters must interact with their environment, not just exist in it:
- leaning a shoulder against a wall rather than standing near it
- stepping around a puddle, not just walking down an alley
- a hand brushing a door frame as they pass
- reacting to a sound from off-frame
This makes scenes feel lived-in, not staged.

RULE 6 — NEVER WRITE "WATCHING AS"
This is the most common trap in passive direction. "Watching as X happens" makes the character an observer and weakens the shot.
Wrong: "he watches as the gates slowly open"
Wrong: "she watches as the crowd disperses"
Right: remove the observer entirely — show the event directly: "the northern gates creak open, the sound carrying across the empty square"
Right: show the character's internal reaction instead: "he goes still, his eyes fixed on something just off frame"

RULE 7 — CAMERA: ONE IDEA PER SHOT, NO STACKING
Every shot has exactly one camera idea. A shot size is one idea. A movement is one idea. An angle is one idea. Never combine more than two.

Wrong (stacking three): "close-up on his face, medium-wide shot with a low angle pan upward" — three conflicting ideas
Wrong (stacking two moves): "slow push-in with a low angle pan" — two movements
Right: "close-up, static locked" — size + stillness
Right: "medium shot, slow push-in" — size + one movement
Right: "low angle medium shot" — angle + size, no movement needed

Shot sizes: wide shot, medium shot, medium-wide shot, close-up, over-the-shoulder, low angle medium shot
Movements: slow push-in, subtle push-in, slow downward pan, slow pan upward, handheld drift, gentle tracking forward, static locked

Watch your defaults — these are becoming predictable:
- "gentle tracking forward" → overused; replace with static locked or subtle push-in
- "low angle pan up / pan upward" → replace with "low angle static frame" — far more powerful for authority/reveals
- "slow pan upward" on a close-up → impossible to execute cleanly; use static instead

Never use: dolly zoom, zoom in, aerial tilt down, pipe characters

RULE 8 — MATCH CAMERA SIZE TO FOCAL DETAIL
Wide → isolation, environment, body language at a distance
Medium → emotional performance, reactions, character presence
Close-up → one intense detail: a hand, an eye, an object
A wide shot cannot show a finger trembling. A close-up cannot show loneliness in a crowd. Size and content must match.

RULE 9 — CONTRAST BETWEEN SHOTS WITHIN A BEAT
Each shot in a beat must contrast the previous on at least two axes:
- Motion vs stillness (moving camera → static locked)
- Scale (wide → close-up → medium)
- Lighting quality (warm → cool, bright → shadow)
- Subject (character → environment → object cutaway)
If all shots in a beat share the same camera size and pacing, they feel like one repeated shot. Break the pattern deliberately.
Include 1–2 bold shots per episode: a silhouette, an extreme close-up, a stark lighting contrast. These become the visual anchors the audience remembers.

RULE 10 — BEATS MUST ADVANCE THE STORY
Before writing each beat, ask: what is different about the situation at the END of this beat vs. the START?
If the answer is "nothing — it's the same moment re-shot," the beat is wrong. Rewrite it.
Wrong: Beat 1 = pushing Raul toward pantry, Beat 2 = pushing Raul into pantry → same action, different angle
Right: Beat 1 = the struggle (external), Beat 2 = inside the pantry (new space, new tension, new perspective)
Each beat must change: the location, the emotional state, the power dynamic, or the information the audience has.

RULE 10B — EACH BEAT NEEDS A DISTINCT VISUAL IDENTITY
Consecutive beats must feel different. Before writing Beat N, check Beat N-1: same lighting? same camera distance? same tone? Change at least two.
Example progression: physical/kinetic → tight/claustrophobic → wide/exterior → somber/still
Exposition beats (information being delivered) need their own visual identity — harsher light, tighter framing, slower pacing — so the audience registers this as the stakes moment.

RULE 10C — ANCHOR SHOTS (required: 1–2 per episode)
Every episode must contain at least one anchor shot — a visually dominant moment the viewer will remember.
Anchor shot types: extreme close-up with zero motion, a silhouette in a doorway, a wide locked frame with an unexpected reveal, a subject's POV from a constrained space (inside a pantry, behind a door).
Anchor shots carry no camera movement. They hold. That's what makes them land.
Place anchor shots at the highest-stakes moment of the episode — the reveal, the threat, the turning point.

RULE 10D — SPATIAL BLOCKING
Characters must occupy specific positions in the frame. Vague staging ("they stand near each other") creates flat scenes.
Always define: who is closest to the exit, who has their back to the door, who physically blocks whom.
This makes power dynamics visible without dialogue. A character who stands between two others is protecting — or controlling.
When characters move, say where they end up, not just that they moved.

RULE 11 — VISUALIZE THE CONCEPT, NOT JUST THE ACTION
Find the visual beneath the surface of the beat.
Fear or hesitation → fingers pause, breath visible, body goes still
Erasure / low importance → text that flickers, a page that fades at the edges, shadows that don't quite hold
Revelation → hands stop moving, eyes widen slightly, the room blurs behind
Artificiality / staged world → unnaturally rigid document layout, faint system-like glow on objects
Grief → flowers held too tightly, eyes that don't blink, stillness against surrounding motion
Add at least one element of invisible storytelling per beat — something the viewer feels but doesn't consciously notice.

RULE 12 — MOTION DISCIPLINE AND SHOT IDENTITY
Each shot commits to ONE identity. Motion OR stillness OR a lighting choice OR a composition technique — not all at once.

Max ONE motion element per shot. Many shots should have zero motion — stillness is not laziness, it is precision.

Target distribution across the episode:
- 40% still: locked frame, held expression, no motion noted
- 40% subtle: one slow micro-motion (breath, a finger, a shadow deepening)
- 20% active: one clear visible motion matched to the scene's energy

Match energy to scene type — this is non-negotiable:
- Kinetic / action (fight, chase, physical task) → fast, effortful, slightly unsteady motion; forceful body language
- Tense / discovery → cautious stillness, single slow reveal
- Emotional / reflective → micro-motion only, or none; let the face carry it
- Crowd / busy → one environmental element (background figures shifting, voices overlapping)
- Revelation / shock → zero motion — frame locks, world goes still

Lighting motion (flickering, shadows) must mean something:
- Tension → unstable flicker
- Calm → steady, no note needed
- Fear → light failing or dimming
- Never use "candlelight flickering faintly" as a default tail — only write it when candlelight instability is meaningful to the shot

No phrase may appear more than twice in an entire episode. If you've already written "candlelight flickering faintly" twice, find a different ending or leave it blank.

Lighting options to rotate: warm amber candlelight / cool diffused daylight / harsh rim light / dim overcast fill / deep chiaroscuro / cold blue shadow / torchlight casting uneven warmth

RULE 13 — ACTION AND TENSION SCENES: CREATE SPIKES
In heist, combat, chase, or high-stakes scenes, the sequence must contain at least two tension spikes — moments where the pacing or energy shifts abruptly.
A tension spike is: something goes unexpectedly still, or something moves faster than expected, or the environment becomes threatening.
Without spikes, action scenes read as controlled and composed — the opposite of danger.

Techniques for tension spikes:
- Sound drop: "the surrounding noise cuts out as he rounds the corner, the silence immediate and wrong"
- Visual isolation: a character suddenly alone in frame where others were
- Environmental threat: a shadow that doesn't belong, a door left open that should be closed
- Stillness as weapon: a reveal shot with zero movement — locked wide, subject silhouetted, nothing moves
- Pacing break: after 3 medium shots, one extreme close-up with no movement — the sudden scale change creates unease

Every action scene should also have at least one dominant still frame. Stillness in tension = threat, control, danger. A locked wide shot of a silhouetted figure is more threatening than a shot with camera movement.

RULE 14 — DIALOGUE SCENES: STILLNESS IS POWER
In conversation beats, the more intense the dialogue, the less the camera should move.
Reaction shots during dialogue → static locked or minimal push-in, never tracking
Group dialogue coverage → rotate: reaction / response / group context — one shot each, no repeating the same angle
Intense confrontation → locked close-up, no movement at all
Light conversation → one gentle move allowed, then hold

RULE 15 — MEMORY AND RECALL SHOTS
When a beat involves a character remembering something, the shot must feel visually distinct from regular present-tense shots.
Techniques: slightly shallow focus, cooler or more desaturated lighting, the character's body going still while the environment stays active
Wrong: same medium shot with static locked — looks identical to a normal beat
Right: "close-up, his eyes unfocusing slightly as his hand stills on the document, the room behind him softening, cool overcast light"

RULE 16 — CROWD AND MULTI-SUBJECT RISK
In conversation beats, the more intense the dialogue, the less the camera should move.
Reaction shots during dialogue → static locked or minimal push-in, never tracking
Group dialogue coverage → rotate: reaction / response / group context — one shot each, no repeating the same angle
Intense confrontation → locked close-up, no movement at all
Light conversation → one gentle move allowed, then hold

RULE 17 — LENGTH
25-40 words. One subject. One action. One camera move.
The video AI weights the first 20 words most. Lead with style tags + character + action.
Cut everything after the first complete image is painted — do not pad.

EXAMPLE:
(Korean manhwa, BL romance, rich jewel tones), young man with dark hair, slowly lowering a document as the meaning hits him, dim candlelit room, medium shot slow pan down toward his hands, warm amber shadows

Also extract any spoken dialogue in this beat into a "dialogue" list (speaker + exact line).
If a beat has no dialogue, omit the "dialogue" field.

HOOK SCORING (required for every beat):

hook_intensity — score 1–4, assigned once per episode across all beats:
  4 = strongest hook in the episode. The moment that makes a viewer stop scrolling. Unexpected, tense, or emotionally charged. There is exactly ONE beat scored 4 per episode.
  3 = builds tension or adds mystery. The second-most compelling beat. Exactly ONE beat scored 3.
  2 = emotional or conflict peak. A beat with clear stakes or feeling. ONE or TWO beats scored 2.
  1 = all remaining beats. Setup, exposition, transitions.
Rules: scores must be distributed — do not give multiple beats the same high score. Every episode must have exactly one 4, one 3, and at least one 2.

hook_line — one short punchy subtitle line (8 words max) written for the beat scored 3 or 4 only.
This line appears as the first-frame subtitle when this beat becomes a short-form clip.
It must create immediate curiosity or urgency. Written in present tense. No character names.
Good: "If she finds him, he's dead." / "He wasn't supposed to be here." / "This is where it all breaks."
Bad: "Leonardo pushes Raul into the pantry." / "They discuss the trial."
Omit hook_line for beats scored 1 or 2.

Output ONLY valid JSON with NO code fences, no markdown, no explanation — raw JSON only:
{
  "synopsis": "3-4 sentence summary here.",
  "beats": [
    {
      "beat": "one sentence describing what happens in this beat",
      "hook_intensity": 4,
      "hook_line": "If she finds him, he's dead.",
      "dialogue": [
        {"speaker": "Character Name", "line": "Exact spoken line from the text."},
        {"speaker": "Other Character", "line": "Their reply."}
      ],
      "shots": [
        "prompt here",
        "prompt here"
      ]
    }
  ]
}"""

ART_STYLE_DEFAULT = "masterpiece, best quality, Korean manhwa, BL romance, rich jewel tones, delicate lineart"


def _build_system_prompt(art_style: str = "", novel_dir: str = "") -> str:
    style = art_style.strip() if art_style else ART_STYLE_DEFAULT
    prompt = DIRECTOR_SYSTEM_TEMPLATE.replace("{ART_STYLE}", style)
    if novel_dir:
        from video.soul_parser import build_soul_context
        soul_context = build_soul_context(novel_dir, ["lighting_palette", "world_aesthetic", "tone", "avoid"])
        if soul_context:
            prompt = soul_context + "\n\n" + prompt
    return prompt


def _parse_response(raw: str) -> tuple[str, list[dict]]:
    """
    Extract synopsis + beats from model output.
    Returns (synopsis_str, beats_list). Falls back to ("", []) on failure.
    """
    if "<think>" in raw:
        raw = raw.split("</think>")[-1].strip()

    # Strip markdown code fences if model wrapped output in ```json ... ```
    if "```" in raw:
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

    # Try new {synopsis, beats} object format first
    obj_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            if isinstance(data, dict) and "beats" in data:
                synopsis = data.get("synopsis", "")
                beats = _validate_beats(data["beats"])
                if beats:
                    return synopsis, beats
        except json.JSONDecodeError:
            pass

    # Fall back to bare array format (old prompt style)
    arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if arr_match:
        try:
            beats = _validate_beats(json.loads(arr_match.group(0)))
            if beats:
                return "", beats
        except json.JSONDecodeError:
            pass

    return "", []


def _validate_beats(raw_beats) -> list[dict]:
    valid = []
    for b in raw_beats:
        if isinstance(b, dict) and "beat" in b and "shots" in b:
            shots = b["shots"]
            if isinstance(shots, list) and len(shots) >= 2:
                entry = {"beat": b["beat"], "shots": [_ensure_motion(s) for s in shots[:4]]}
                if "hook_intensity" in b:
                    try:
                        entry["hook_intensity"] = int(b["hook_intensity"])
                    except (ValueError, TypeError):
                        entry["hook_intensity"] = 1
                else:
                    entry["hook_intensity"] = 1
                if "hook_line" in b and isinstance(b["hook_line"], str) and b["hook_line"].strip():
                    entry["hook_line"] = b["hook_line"].strip()
                if "dialogue" in b and isinstance(b["dialogue"], list):
                    entry["dialogue"] = b["dialogue"]
                valid.append(entry)
    return valid


def _fallback_entry() -> tuple[str, list[dict]]:
    s = ART_STYLE_DEFAULT
    return "", [{"beat": "scene", "shots": [
        f"({s}), young man with dark hair standing alone, looking into the distance, ruined stone courtyard with overgrown vines, slow aerial tilt down, golden sunset casting long shadows, melancholic solitude, wind moving his hair and coat gently",
        f"({s}), young man with dark hair walking forward with determined expression, cobblestone street with dim lanterns, low angle tracking shot, soft diffused rim light, tense anticipation, dust drifting at his feet",
        f"({s}), young man's face in close-up showing shock and realization, blurred crowd background, slow push-in on face, dramatic chiaroscuro, quiet reverence, breath visible in cold air",
        f"({s}), ornate letter or glowing item held in trembling hands, dark wooden table with candlelight, over-the-shoulder pan, warm candlelight flickering, somber grief, flame casting dancing shadows",
    ]}]


def _write_prompts_txt(ch_num: int, filename: str, synopsis: str,
                       beats: list[dict], batch_dir: str, clips_dir: str = "") -> None:
    """Write a plain-text version of the storyboard for Higgsfield copy-paste."""
    ch_dir = os.path.join(batch_dir, f"chapter-{ch_num:03d}")
    os.makedirs(ch_dir, exist_ok=True)

    title = filename.replace(".txt", "")
    sep = "=" * 64
    dash = "-" * 64
    lines = [
        f"CHAPTER {ch_num:03d} — {title}",
        sep,
    ]
    if synopsis:
        lines += [f"SYNOPSIS: {synopsis}", ""]
    if clips_dir:
        lines += [f"Drop clips in: {os.path.abspath(clips_dir)}", ""]

    for b_idx, beat in enumerate(beats, 1):
        lines += [dash, f"BEAT {b_idx}: {beat['beat']}", ""]
        for s_idx, shot in enumerate(beat["shots"], 1):
            clip_name = f"chapter-{ch_num:03d}-beat-{b_idx}-shot-{s_idx}.mp4"
            lines += [
                f"  SHOT {s_idx}  →  {clip_name}",
                f"  {shot}",
                "",
            ]

    lines.append(dash)
    with open(os.path.join(ch_dir, "prompts.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _ensure_motion(shot: str) -> str:
    """No-op — motion discipline is now enforced by the system prompt, not post-processing."""
    return shot


def _build_cast_hint(primary_char_name: str, chapter_text: str,
                     characters: list[dict]) -> str:
    """Build a CAST PROFILES block using only manually curated characters (those with pronoun set)."""
    if not characters:
        return ""

    # Only use canonical characters — those with an explicit pronoun field
    canonical = [c for c in characters if "pronoun" in c]
    if not canonical:
        return ""

    char_lookup = {c["name"].lower(): c for c in canonical}
    featured: list[dict] = []

    # Always lead with the primary character
    if primary_char_name:
        char = char_lookup.get(primary_char_name.lower())
        if char:
            featured.append(char)

    # Add up to 2 more canonical characters with ≥3 mentions in the chapter
    text_lower = chapter_text.lower()
    for c in canonical:
        if len(featured) >= 3:
            break
        if c in featured:
            continue
        name = c.get("name", "")
        if len(name) >= 3 and text_lower.count(name.lower()) >= 3:
            featured.append(c)

    if not featured:
        return ""

    lines = ["CAST PROFILES — use these exact descriptors and pronouns in every shot:"]
    for c in featured:
        name = c.get("name", "")
        pronoun = c.get("pronoun", "he/him")
        desc = c.get("description", "").replace("\n", " ").strip()
        if len(desc) > 180:
            desc = desc[:180].rsplit(" ", 1)[0] + "..."
        lines.append(f"- {name} ({pronoun}): {desc}")

    return "\n".join(lines)


def write_director_prompts(chapters: list[dict], prompts_dir: str,
                           primary_characters: dict | None = None,
                           art_style: str = "",
                           characters: list[dict] | None = None) -> list[dict]:
    """
    For each chapter, generate beat-level storyboard prompts via LM Studio.
    chapters: list of {filename, text} dicts (from segmenter)
    primary_characters: optional {filename: character_name} for character-aware prompts
    art_style: visual style suffix appended to every shot prompt
    characters: full character list from characters.json for cast profile injection
    Returns chapters with added 'beats' field.
    """
    os.makedirs(prompts_dir, exist_ok=True)
    primary_characters = primary_characters or {}
    characters = characters or []

    # Derive sibling paths
    batch_dir = os.path.join(os.path.dirname(prompts_dir), "batch")
    novel_dir = os.path.dirname(prompts_dir)  # novels/<slug>/video/../ → novels/<slug>
    novel_dir = os.path.dirname(os.path.dirname(prompts_dir))  # novels/<slug>/video/director_prompts → novels/<slug>
    system_prompt = _build_system_prompt(art_style, novel_dir=novel_dir)
    clips_dir = os.path.join(os.path.dirname(prompts_dir), "clips")

    results = []
    print(f"  Writing storyboard prompts for {len(chapters)} chapters...")

    for i, ch in enumerate(chapters, 1):
        filename = ch["filename"]
        cache_path = os.path.join(prompts_dir, filename.replace(".txt", ".json"))

        m = re.search(r'(\d+)', filename)
        ch_num = int(m.group(1)) if m else i

        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            ch["beats"] = cached["beats"]
            ch["synopsis"] = cached.get("synopsis", "")
            _write_prompts_txt(ch_num, filename, ch["synopsis"], ch["beats"], batch_dir, clips_dir)
            print(f"  [{i}/{len(chapters)}] {filename} (cached, {len(ch['beats'])} beats)")
            results.append(ch)
            continue

        char_name = primary_characters.get(filename, "")
        cast_hint = _build_cast_hint(char_name, ch["text"], characters)
        user_content = f"{cast_hint}\n\nCHAPTER TEXT:\n{ch['text'][:3000]}" if cast_hint else f"CHAPTER TEXT:\n{ch['text'][:3000]}"

        print(f"  [{i}/{len(chapters)}] {filename}...", end=" ", flush=True)
        try:
            resp = _client.chat.completions.create(
                model=LM_STUDIO_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
                max_tokens=10000,
            )
            raw = resp.choices[0].message.content.strip()
            synopsis, beats = _parse_response(raw)
            if beats:
                print(f"done ({len(beats)} beats)")
            else:
                synopsis, beats = _fallback_entry()
                print("fallback (parse failed)")
        except Exception as e:
            synopsis, beats = _fallback_entry()
            print(f"fallback ({e})")

        ch["beats"] = beats
        ch["synopsis"] = synopsis
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"filename": filename, "synopsis": synopsis, "beats": beats},
                      f, indent=2, ensure_ascii=False)
        _write_prompts_txt(ch_num, filename, synopsis, beats, batch_dir, clips_dir)
        results.append(ch)

    print(f"  Storyboard prompts saved to: {prompts_dir}")
    print(f"  TIP: Edit .json files in {prompts_dir} to refine prompts before generating video.")
    return results
