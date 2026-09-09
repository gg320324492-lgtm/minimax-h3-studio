#!/bin/bash
# EP01 rerun post chain: selection -> timeline -> upscale -> audio -> subtitles -> final -> QA
set -e
cd /e/Minimax-H3/ceo_mindread_ep01
PY="E:/ComfyUI/venv/Scripts/python.exe"
EDIT=07_edit

echo "===== [1/7] select_takes ====="
"$PY" scripts/select_takes.py

echo "===== [2/7] build_timeline ====="
"$PY" scripts/build_timeline.py

echo "===== [3/7] upscale 720p -> 1440p (pipe_4k_fast, chain quality path) ====="
time "$PY" /e/Minimax-H3/pipe_4k_fast.py "$EDIT/EP01_PICTURE_LOCK_720P.mp4" "$EDIT/EP01_UPSCALED_1440p.mp4" /e/Minimax-H3/work_frames/ep01_rerun_up

echo "===== [4/7] Lanczos 1440p -> 1080p master ====="
ffmpeg -y -loglevel error -i "$EDIT/EP01_UPSCALED_1440p.mp4" \
  -vf "scale=1080:1920:flags=lanczos" -c:v libx264 -crf 18 -pix_fmt yuv420p \
  "$EDIT/EP01_PICTURE_MASTER_1080P.mp4"

echo "===== [5/7] audio mix v4 ====="
"$PY" scripts/mix_audio_v4.py

echo "===== [6/7] burn subtitles v2 ====="
"$PY" scripts/burn_subtitles_v2.py

echo "===== [7/7] finalize + QA ====="
"$PY" scripts/finalize.py
"$PY" scripts/qa_final.py

echo "===== POST CHAIN DONE ====="
