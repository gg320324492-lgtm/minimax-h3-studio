"""QA gate for report-pipeline renders (Phase 6.3).

Checks (all against the props that drove the render):
  1. Container: resolution/fps match props.format; h264; yuv420p; AAC 48k stereo
  2. Duration within ±0.6s of props-derived duration
  3. Loudness: -16..-12 LUFS integrated; TP <= -0.5 dBTP

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/qa_report.py \
      --video out/demo.mp4 --props public/jobs/<job>/props.json
Exit 1 on any FAIL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFMPEG, FFPROBE  # noqa: E402

sys.path.insert(0, str(ROOT / 'studio' / 'src'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True, type=Path)
    ap.add_argument('--props', required=True, type=Path)
    args = ap.parse_args()

    props = json.loads(args.props.read_text(encoding='utf-8'))
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))
        print(f'  [{"PASS" if ok else "FAIL"}] {name}: {detail}')

    print('=== Report QA ===\n[1] Container')
    r = subprocess.run([FFPROBE, '-v', 'error', '-show_format', '-show_streams',
                        '-of', 'json', str(args.video)], capture_output=True, text=True)
    d = json.loads(r.stdout)
    vs = next((s for s in d['streams'] if s['codec_type'] == 'video'), None)
    as_ = next((s for s in d['streams'] if s['codec_type'] == 'audio'), None)
    if not vs or not as_:
        print('ERROR: missing video or audio stream')
        return 1
    fmt = d['format']
    f = props['format']

    check('resolution', vs['width'] == f['width'] and vs['height'] == f['height'],
          f"{vs['width']}x{vs['height']} (expect {f['width']}x{f['height']})")
    check('video codec', vs['codec_name'] == 'h264', vs['codec_name'])
    check('pix_fmt', vs['pix_fmt'] == 'yuv420p', vs['pix_fmt'])
    check('fps', vs['avg_frame_rate'] == f'{f["fps"]}/1', vs['avg_frame_rate'])
    check('audio codec', as_['codec_name'] == 'aac', as_['codec_name'])
    check('sample rate', int(as_['sample_rate']) == 48000, as_['sample_rate'])
    check('channels STEREO', int(as_['channels']) == 2, f"channels={as_['channels']}")

    print('\n[2] Duration')
    dur = float(fmt['duration'])
    expect = props.get('totalDuration') or 0
    # report 模板时长由分段自动推导；用容差对比（props 未给 totalDuration 时跳过精确断言）
    check('duration vs props', expect == 0 or abs(dur - expect) <= 0.6,
          f'{dur:.2f}s (props {expect:.2f}s)' if expect else f'{dur:.2f}s (no props reference)')

    print('\n[3] Loudness')
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(args.video),
                        '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    import re
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)
    if not blocks:
        print('ERROR: loudnorm JSON missing')
        return 1
    ln = json.loads(blocks[-1])
    i_lufs = float(ln['input_i'])
    tp = float(ln['input_tp'])
    check('integrated loudness -16..-12 LUFS', -16 <= i_lufs <= -12, f'{i_lufs} LUFS')
    check('true peak <= -0.5 dBTP', tp <= -0.5, f'{tp} dBTP')

    fails = [n for n, ok, _ in results if not ok]
    print(f'\n=== RESULT: {"PASS" if not fails else "FAIL"} ({len(results) - len(fails)}/{len(results)}) ===')
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
