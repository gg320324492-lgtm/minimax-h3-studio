#!/bin/bash
# liaozhai_demo v2 post chain: timeline -> picture lock -> AnimeSharpV4 SR -> postfx -> audio -> subs -> final -> QA
set -e
cd /e/Minimax-H3/liaozhai_demo
PY="E:/ComfyUI/venv/Scripts/python.exe"
SR="E:/Minimax-H3/sr_pipeline_v2.py"
EDIT=07_edit
FROM_STAGE="${FROM_STAGE:-1}"

stage() {
  if [ "$1" -lt "$FROM_STAGE" ]; then
    echo "----- [skip $1] $2 (FROM_STAGE=$FROM_STAGE) -----"
    return 1
  fi
  echo "===== [$1/7] $2 ====="
  return 0
}

if stage 1 "build_timeline"; then
  "$PY" scripts/build_timeline.py
fi

if stage 2 "picture lock (title card + normalize 720p + end card + concat)"; then
  "$PY" scripts/edit_picture.py
fi

if stage 3 "SR x4 (AnimeSharpV4 2-pass, fp32) -> 2880p intermediate"; then
  time "$PY" "$SR" "$EDIT/LZ_PICTURE_LOCK_1280x720.mp4" "$EDIT/LZ_MASTER_4X.mp4" \
    --model animev4fast --scale 2 --passes 2 \
    --tile 768 --overlap 64 --fbatch 4 \
    --no-half \
    --codec x264 --crf 14 --preset fast \
    --audio none
fi

if stage 4 "final 1080p: lanczos + CAS 0.35 + fine grain"; then
  "$PY" scripts/postfx_1080.py "$EDIT/LZ_MASTER_4X.mp4" "$EDIT/LZ_MASTER_1080P.mp4" \
    --cas 0.35 --grain 2 --crf 16
fi

if stage 5 "audio mix"; then
  "$PY" scripts/mix_audio.py
fi

if stage 6 "burn subtitles"; then
  "$PY" scripts/burn_subtitles.py
fi

if stage 7 "finalize + QA"; then
  "$PY" scripts/finalize.py
  "$PY" scripts/qa_final.py
fi

echo "===== POST CHAIN V2 DONE (from stage $FROM_STAGE) ====="
