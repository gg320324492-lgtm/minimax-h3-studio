"""Emit Phase-0 dummy timeline props + hardlink EP01 assets into studio/public/jobs/phase0/.

Reads ceo_mindread_ep01/00_project/timeline.json (v1), probes real frame counts of
04_video_selected clips, and writes a DramaVertical props JSON. Assets are hardlinked
(same drive) so no copies are made.

Run with any python that has stdlib only:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/emit_phase0_props.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EP01 = os.path.join(ROOT, "ceo_mindread_ep01")
FFPROBE = os.path.join(ROOT, "tools", "ffmpeg-7.1.1-full_build", "bin", "ffprobe.exe")
OUT_DIR = os.path.join(ROOT, "studio", "public", "jobs", "phase0")
FPS = 24


def probe_frames(path: str) -> int:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True,
    )
    return int(out.stdout.strip())


def link_into(src: str, dst_name: str) -> str:
    dst = os.path.join(OUT_DIR, dst_name)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return dst


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(os.path.join(EP01, "00_project", "timeline.json"), encoding="utf-8") as f:
        tl = json.load(f)

    shots = []
    for shot_id, boundary in tl["shot_boundaries"].items():
        clip = os.path.join(EP01, "04_video_selected", f"{shot_id}.mp4")
        if not os.path.exists(clip):
            print(f"MISSING clip for {shot_id}: {clip}", file=sys.stderr)
            return 1
        link_into(clip, f"{shot_id}.mp4")
        frames = probe_frames(clip)
        # 呈现帧数以 boundary 时长换算为准；源片段更长时由 trimBefore 截断，
        # Phase 0 选片即呈现（等长），两者应一致。
        present = round(boundary["duration"] * FPS)
        if present != frames:
            print(f"note: {shot_id} source={frames}f boundary={present}f -> use min")
        shots.append({
            "id": shot_id,
            "file": f"jobs/phase0/{shot_id}.mp4",
            "durationInFrames": min(present, frames),
        })

    premixed_src = os.path.join(EP01, "07_edit", "EP01_WITH_AUDIO.mp4")
    if not os.path.exists(premixed_src):
        print(f"MISSING premixed audio source: {premixed_src}", file=sys.stderr)
        return 1
    link_into(premixed_src, "PREMIXED.mp4")

    props = {
        "version": 0,
        "project": "ceo_mindread_ep01_phase0",
        "format": {"width": 1080, "height": 1920, "fps": FPS},
        "shots": shots,
        "audioBus": {"premixed": "jobs/phase0/PREMIXED.mp4"},
        "subtitles": [
            {"id": e["id"], "text": e["text"], "style": e["style"], "start": e["start"], "end": e["end"]}
            for e in tl["subtitle_events"]
        ],
    }

    props_path = os.path.join(OUT_DIR, "timeline_v2.json")
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    total = sum(s["durationInFrames"] for s in shots)
    print(f"props: {props_path}")
    print(f"shots: {len(shots)}, total frames: {total} ({total / FPS:.3f}s)")
    print(f"subtitles: {len(props['subtitles'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
