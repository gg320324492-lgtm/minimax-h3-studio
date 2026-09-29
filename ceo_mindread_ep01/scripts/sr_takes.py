"""Per-take Real-ESRGAN super-resolution for Remotion assembly (Phase 1).

04_video_selected/<SID>.mp4 (768x1344) -> 04_video_selected_sr/<SID>_1080.mp4 (1080x1920)

Uses the exact model/tile parameters approved for EP01 in UPGRADE_REPORT_20260919.md
(x2plus fp16, tile 768, overlap 64, x264 crf18), but per-take so the Remotion layer
assembles at native 1080x1920 instead of re-encoding an SR'd master.

Run under the ComfyUI venv (torch + basichsr deps live there):
  E:/ComfyUI/venv/Scripts/python.exe ceo_mindread_ep01/scripts/sr_takes.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
EP01 = ROOT / 'ceo_mindread_ep01'
SR_SCRIPT = ROOT / 'sr_pipeline_v2.py'
VENV_PY = r'E:\ComfyUI\venv\Scripts\python.exe'

SR_ARGS = ['--scale', '2', '--tile', '768', '--overlap', '64',
           '--out-width', '1080', '--out-height', '1920', '--audio', 'none']


def main() -> int:
    manifest = json.loads((EP01 / '00_project' / 'shot_manifest.json').read_text(encoding='utf-8'))
    order = list(manifest['selections'].keys())

    failed = []
    for i, sid in enumerate(order):
        src = EP01 / '04_video_selected' / f'{sid}.mp4'
        dst_dir = EP01 / '04_video_selected_sr'
        dst_dir.mkdir(exist_ok=True)
        dst = dst_dir / f'{sid}_1080.mp4'
        if dst.exists():
            print(f'[{i + 1}/{len(order)}] {sid}: exists, skip', flush=True)
            continue
        print(f'[{i + 1}/{len(order)}] SR {sid} ...', flush=True)
        r = subprocess.run([VENV_PY, str(SR_SCRIPT), str(src), str(dst)] + SR_ARGS)
        if r.returncode != 0:
            print(f'{sid}: FAILED rc={r.returncode}', flush=True)
            failed.append(sid)
        # 失败不中断：继续跑其余片段，最后汇总（缺的片段在 staging 时会被 prop 校验拦下）

    if failed:
        print(f'FAILED takes: {failed}', file=sys.stderr)
        return 1
    print('all takes SR done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
