#!/usr/bin/env bash
# Tests director prompt generation speed for chapter 1.
# Pass 1: thinking ON. If > 60 min, auto-switches to /no_think and retries.
# Reports timing for each pass and recommendation.

set -euo pipefail

NOVEL="if-you-dont-become-the-main-character-youll-die"
PROJ="/Users/aicomputer/Desktop/Webnovels"
DIRECTOR="$PROJ/video/director.py"
PROMPTS_DIR="$PROJ/novels/$NOVEL/video/director_prompts"
TIMEOUT_SECS=3600   # 1 hour

run_chapter1() {
    local label="$1"
    local log="$PROJ/pipeline/director_speed_${label}.log"

    # Clear cached prompt so chapter 1 is regenerated
    find "$PROMPTS_DIR" -name "Chapter 001*.json" -delete 2>/dev/null || true

    echo "[test_director_speed] Starting chapter 1 with thinking $label..."
    local start=$SECONDS

    # Run pipeline in background, capture its PID
    cd "$PROJ"
    python3 pipeline/run.py --novel "$NOVEL" --stages batch >"$log" 2>&1 &
    local pid=$!

    # Poll until chapter 1 done or timeout
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        if grep -q "\[2/300\]\|\[1/300\].*done\|fallback (parse" "$log" 2>/dev/null; then
            break
        fi
        sleep 15
        elapsed=$(( SECONDS - start ))
        if [[ $elapsed -ge $TIMEOUT_SECS ]]; then
            echo "[test_director_speed] TIMEOUT after ${elapsed}s — killing batch"
            kill "$pid" 2>/dev/null || true
            echo "TIMEOUT" >"$PROJ/pipeline/director_speed_result_${label}.txt"
            return 1
        fi
    done

    # Stop the batch (we only wanted chapter 1)
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true

    elapsed=$(( SECONDS - start ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))
    echo "[test_director_speed] Chapter 1 done in ${mins}m ${secs}s (thinking $label)"
    echo "${mins}m ${secs}s" >"$PROJ/pipeline/director_speed_result_${label}.txt"

    # Show the generated prompts
    echo "--- Synopsis + beats preview ---"
    local cache=$(ls "$PROMPTS_DIR"/Chapter\ 001*.json 2>/dev/null | head -1)
    if [[ -n "$cache" ]]; then
        python3 -c "
import json, sys
d = json.load(open('$cache'))
print('SYNOPSIS:', d.get('synopsis','(none)'))
print()
for i, b in enumerate(d.get('beats',[]), 1):
    print(f'Beat {i}: {b[\"beat\"]}')
    for j, s in enumerate(b['shots'], 1):
        print(f'  Shot {j}: {s}')
"
    fi
    return 0
}

enable_think() {
    # Ensure /no_think prefix is NOT in director.py
    sed -i '' 's|f"/no_think\\\\n{char_hint}|f"{char_hint}|g' "$DIRECTOR" 2>/dev/null || true
}

disable_think() {
    # Add /no_think prefix if not already present
    python3 - <<'PY'
import re, sys
path = "/Users/aicomputer/Desktop/Webnovels/video/director.py"
text = open(path).read()
if '/no_think' not in text:
    text = text.replace(
        'f"{char_hint}\\n\\nCHAPTER TEXT:\\n{ch[\'text\'][:3000]}"',
        'f"/no_think\\n{char_hint}\\n\\nCHAPTER TEXT:\\n{ch[\'text\'][:3000]}"'
    )
    open(path, 'w').write(text)
    print("thinking disabled")
else:
    print("already disabled")
PY
}

# ── Pass 1: thinking ON ─────────────────────────────────────────────────────
enable_think
if run_chapter1 "ON"; then
    result_on=$(cat "$PROJ/pipeline/director_speed_result_ON.txt")
    echo ""
    echo "============================================================"
    echo "  Result: Chapter 1 with thinking ON finished in $result_on"
    echo "  300 chapters estimate: ~$(python3 -c "
mins=$(echo "$result_on" | grep -oE '[0-9]+m' | tr -d 'm' || echo 0)
secs=$(echo "$result_on" | grep -oE '[0-9]+s' | tr -d 's' || echo 0)
total_mins = int('${mins:-0}') * 300 + int('${secs:-0}') * 300 // 60
print(f'{total_mins // 60}h {total_mins % 60}m')
" 2>/dev/null || echo "unknown")"
    echo "  Thinking ON is fast enough — recommend keeping it on for quality."
    echo "============================================================"
    exit 0
fi

# ── Pass 2: thinking OFF ────────────────────────────────────────────────────
echo ""
echo "[test_director_speed] Thinking ON timed out. Switching to /no_think..."
disable_think

if run_chapter1 "OFF"; then
    result_off=$(cat "$PROJ/pipeline/director_speed_result_OFF.txt")
    echo ""
    echo "============================================================"
    echo "  Result: Chapter 1 with thinking OFF finished in $result_off"
    echo "  Thinking ON: TIMEOUT (>60 min)"
    echo "  Recommendation: use /no_think for all 300 chapters."
    echo "  Run: python3 pipeline/run.py --novel $NOVEL --stages batch"
    echo "============================================================"
    exit 0
fi

# ── Both timed out ───────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Both thinking ON and OFF timed out after 60 min each."
echo "  LM Studio / qwen3.5-9b is too slow for this hardware config."
echo "  Consider: smaller model (3B), cloud API, or DomoAI when ready."
echo "============================================================"
exit 2
