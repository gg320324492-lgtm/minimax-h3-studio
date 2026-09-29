#!/bin/bash
# third_lantern post chain:
# timeline -> picture lock(1344x768) -> FlashVSR 2x -> postfx 1440p -> mix -> burn -> finalize -> QA
set -e
cd /e/Minimax-H3/third_lantern
PY="E:/ComfyUI/venv/Scripts/python.exe"
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

if stage 2 "picture lock (title card + normalize 768p + end card + concat)"; then
  "$PY" scripts/edit_picture.py
fi

if stage 3 "FlashVSR v1.1 scale=2 -> 2688x1536"; then
  time "$PY" scripts/upscale_2k.py "$EDIT/TL_PICTURE_LOCK_1344x768.mp4" "$EDIT/TL_MASTER_4X.mp4" tiny-long
fi

if stage 4 "final 1440p: crop 16:9 + lanczos + CAS + grain"; then
  "$PY" scripts/postfx_final.py "$EDIT/TL_MASTER_4X.mp4" "$EDIT/TL_MASTER_1440P.mp4" \
    --w 2560 --h 1440 --cas 0.3 --grain 1.5 --crf 16
fi

if stage 5 "audio mix"; then
  "$PY" scripts/mix_audio.py
fi

if stage 6 "burn subtitles (2K)"; then
  "$PY" scripts/burn_subtitles.py
fi

if stage 7 "finalize + QA"; then
  "$PY" scripts/finalize.py
  "$PY" scripts/qa_final.py
fi

echo "===== POST CHAIN DONE (from stage $FROM_STAGE) ====="
