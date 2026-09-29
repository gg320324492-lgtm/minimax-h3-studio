#!/bin/bash
# piyao_2026 post chain: timeline -> picture lock -> 1080p SR -> audio -> subs -> final -> QA
# Prereq: all 15 clips present under 03_video_raw/ (scripts/gen_clips.py).
set -e
cd /e/Minimax-H3/piyao_2026
PY="E:/ComfyUI/venv/Scripts/python.exe"
SR="E:/Minimax-H3/sr_pipeline_v2.py"
EDIT=07_edit
TILE=768
OVERLAP=64
FROM_STAGE="${FROM_STAGE:-1}"

stage() {
  if [ "$1" -lt "$FROM_STAGE" ]; then
    echo "----- [skip $1] $2 (FROM_STAGE=$FROM_STAGE) -----"
    return 1
  fi
  echo "===== [$1/6] $2 ====="
  return 0
}

if stage 1 "build_timeline"; then
  "$PY" scripts/build_timeline.py
fi

if stage 2 "picture lock (normalize + S02 freeze + endcard + concat)"; then
  "$PY" scripts/edit_picture.py
fi

if stage 3 "upscale 864x480 -> 1920x1080 (x4v3 single pass)"; then
  time "$PY" "$SR" "$EDIT/PIYAO_PICTURE_LOCK_864x480.mp4" "$EDIT/PIYAO_MASTER_1080P.mp4" \
    --model x4v3 --scale 4 \
    --tile "$TILE" --overlap "$OVERLAP" \
    --out-width 1920 --out-height 1080 \
    --codec x264 --crf 18 --preset slow \
    --audio none
fi

if stage 4 "audio mix"; then
  "$PY" scripts/mix_audio.py
fi

if stage 5 "burn subtitles"; then
  "$PY" scripts/burn_subtitles.py
fi

if stage 6 "finalize + QA"; then
  "$PY" scripts/finalize.py
  "$PY" scripts/qa_final.py
fi

echo "===== POST CHAIN DONE (from stage $FROM_STAGE) ====="
