#!/bin/bash
# EP01 post chain: selection -> timeline -> upscale -> audio -> subtitles -> final -> QA
#
# 2026-09-19: upscale stage moved from pipe_4k_fast.py to sr_pipeline_v2.py.
# Two changes worth knowing about:
#   1. The old chain encoded TWICE: 720p -> 1440p (SR) -> 1080p (Lanczos), i.e.
#      two lossy generations. v2 does SR + Lanczos in a single encode, so the
#      1080p master is now one generation closer to the source.
#   2. pipe_4k_fast.py forced 24fps on decode and encode. The source is 24fps so
#      it happened to work, but it also drifted the duration (60.625s -> 60.653s).
#      v2 probes and preserves the real frame rate.
# The 1440p intermediate is no longer produced; set KEEP_1440P=1 to also emit it.
#
# SAFE OUTPUT (2026-09-19): the upscale stage no longer writes straight over the
# delivered master. Project convention is that original artefacts are kept and
# revisions are written alongside, so v2 output goes to a suffixed name by
# default. Set PROMOTE=1 to also replace the delivered master -- and even then
# the existing master is first copied to *.pre-v2.bak so the comparison stays
# possible. Never silently overwrite a shipped master.
#
# Env vars this script sets for the downstream stages (mix_audio_v4, finalize,
# qa_final all honour them, so a re-run cannot mix audio onto the old picture or
# have its QA gate validate the previous delivery):
#   EP01_MASTER        which 1080p picture master to mix audio onto
#   EP01_FINAL_DIR     where finalize writes / qa_final reads
#   EP01_DESKTOP_DIR   where finalize mirrors the delivery
# Overrides:
#   PROMOTE=1          replace the delivered master and 09_final/ (backs up first)
#   KEEP_1440P=1       also emit the 1440p intermediate
#   SR_OUT=<path>      write the upscaled picture somewhere else
#   FROM_STAGE=N       start at stage N (1..6). Stages are independent enough to
#                      resume: e.g. FROM_STAGE=3 redoes upscale + everything
#                      downstream without regenerating the 720p picture lock
#                      (which select_takes rewrites, invalidating any earlier
#                      measurements taken against it).
#
# TILE/OVERLAP (2026-09-19): 768/64, chosen by the grid sweep + full-episode
# verification in UPGRADE_REPORT_20260919.md §4.9/§4.12. It beats the previous
# 512/32 on SSIM (0.9629 vs 0.9618 on the full episode), is 1.70x faster
# (209s vs 354s), uses 25% less VRAM, and sits within 0.0003 of the theoretical
# ceiling set by not tiling at all. See §4.8 for why the seam metrics were NOT
# the basis of this choice.
set -e
cd /e/Minimax-H3/ceo_mindread_ep01
PY="E:/ComfyUI/venv/Scripts/python.exe"
SR="E:/Minimax-H3/sr_pipeline_v2.py"
EDIT=07_edit
REPORT=logs/upscale_v2_report.json
TILE=768
OVERLAP=64
KEEP_1440P="${KEEP_1440P:-0}"
PROMOTE="${PROMOTE:-0}"
FROM_STAGE="${FROM_STAGE:-1}"
MASTER="$EDIT/EP01_PICTURE_MASTER_1080P.mp4"
SR_OUT="${SR_OUT:-$EDIT/EP01_PICTURE_MASTER_1080P.v2.mp4}"

stage() {  # stage <n> <label...>  -- skip if we are resuming past it
  if [ "$1" -lt "$FROM_STAGE" ]; then
    echo "----- [skip $1] $2 (FROM_STAGE=$FROM_STAGE) -----"
    return 1
  fi
  echo "===== [$1/6] $2 ====="
  return 0
}

if stage 1 "select_takes"; then
  "$PY" scripts/select_takes.py
fi

if stage 2 "build_timeline"; then
  "$PY" scripts/build_timeline.py
fi

if stage 3 "upscale 768x1344 -> 1080x1920 in one encode (sr_pipeline_v2)"; then
  # x2plus single pass (2x) then Lanczos down to 1080x1920, straight from raw frames.
  time "$PY" "$SR" "$EDIT/EP01_PICTURE_LOCK_720P.mp4" "$SR_OUT" \
    --model x2plus --passes 1 \
    --tile "$TILE" --overlap "$OVERLAP" \
    --out-width 1080 --out-height 1920 \
    --codec x264 --crf 18 --preset slow \
    --audio copy \
    --report "$REPORT"
fi

if [ "$PROMOTE" = "1" ]; then
  echo "===== [3a] promote v2 output to delivered master ====="
  if [ -f "$MASTER" ]; then
    cp -p "$MASTER" "$MASTER.pre-v2.bak"
    echo "  backed up: $MASTER.pre-v2.bak"
  fi
  cp -p "$SR_OUT" "$MASTER"
  echo "  promoted:  $MASTER"
  # Also back up the existing delivery. Promoting overwrites 09_final/, and the
  # project convention is that originals are kept -- without this, the previous
  # delivery would be gone with no way back. Uses a directory copy (not a
  # rename) so the old delivery stays readable in place.
  if [ -d "09_final" ] && [ ! -d "09_final.pre-v2.bak" ]; then
    cp -rp "09_final" "09_final.pre-v2.bak"
    echo "  backed up: 09_final/ -> 09_final.pre-v2.bak/"
  fi
  export EP01_MASTER="$MASTER"
  export EP01_FINAL_DIR="09_final"
  export EP01_DESKTOP_DIR="C:/Users/pc/Desktop/MiniMax-H3-Outputs/EP01_CEO_Mindread/09_final"
else
  # Point the rest of the chain at the v2 picture, and give this run its own
  # output directory. Without these two exports the later stages would keep
  # reading the OLD master and would overwrite the existing delivery.
  export EP01_MASTER="$SR_OUT"
  export EP01_FINAL_DIR="09_final_v2"
  export EP01_DESKTOP_DIR="C:/Users/pc/Desktop/MiniMax-H3-Outputs/EP01_CEO_Mindread/09_final_v2"
  echo "  master     : $SR_OUT (delivered master untouched)"
  echo "  final dir  : $EP01_FINAL_DIR"
  echo "  set PROMOTE=1 to replace the delivered master and 09_final/ instead"
fi

if [ "$KEEP_1440P" = "1" ]; then
  echo "===== [3b] optional 1440p intermediate ====="
  "$PY" "$SR" "$EDIT/EP01_PICTURE_LOCK_720P.mp4" "$EDIT/EP01_UPSCALED_1440p.mp4" \
    --model x2plus --passes 1 --tile "$TILE" --overlap "$OVERLAP" \
    --codec x264 --crf 18 --preset slow --audio copy
fi

if stage 4 "audio mix v4"; then
  "$PY" scripts/mix_audio_v4.py
fi

if stage 5 "burn subtitles v2"; then
  "$PY" scripts/burn_subtitles_v2.py
fi

if stage 6 "finalize + QA"; then
  "$PY" scripts/finalize.py
  "$PY" scripts/qa_final.py
fi

echo "===== POST CHAIN DONE (from stage $FROM_STAGE) ====="
