"""QA gate for report-pipeline renders (Phase 6.3).

Checks (all against the props that drove the render):
  1. Container: resolution/fps match props.format; h264; yuv420p; AAC 48k stereo
  2. Duration within a RELATIVE tolerance of props.totalDuration, and reported
     UNVERIFIABLE when props carry no totalDuration at all
  3. Loudness: -16..-12 LUFS integrated; TP <= -0.5 dBTP

Three outcomes, not two: PASS, FAIL and UNVERIFIABLE. An unverifiable check exits
non-zero, because a gate that cannot verify something must not report success —
the P10 audit found the duration check had never run on the one delivered props
file for exactly that reason.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/qa_report.py \
      --video out/demo.mp4 --props public/jobs/<job>/props.json
Exit 1 on any FAIL, and on any UNVERIFIABLE.
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
    raw_expect = props.get('totalDuration')
    # Relative tolerance, not absolute. The 0.6s this used to allow is 14.75% of a
    # 4s clip and 0.1% of a 10-minute one, so it is simultaneously far too loose on
    # short work and needlessly tight on long work. Measured in the P10 audit: a
    # 0.59s error on a 4s file passed, and the boundary sits exactly at 0.6.
    #
    # UNVERIFIABLE is a third outcome, not a pass. The old code read
    # `expect = props.get('totalDuration') or 0` and then `expect == 0 or ...`, so
    # a props file with no totalDuration skipped the assertion entirely and printed
    # "no props reference" — and `studio/public/jobs/report_demo/props.json`, the
    # ONE delivered props file, has no totalDuration at all. The check had therefore
    # never run on a real render.
    #
    # It is also not derivable in Python. The section COUNT follows from the props
    # fields (1 title + len(stats) + 1 chart + len(takeaways) + 1 outro = 9 for the
    # demo, matching reportSections exactly), but the per-section DURATIONS are
    # TypeScript literals in `schemas/report-data.ts` — `t += 3`, `t += 2.4`,
    # `t += 5 + items*0.9` — which reproduce here would duplicate four magic numbers
    # that already exist once and would drift. So the producer must carry
    # `totalDuration`, and its absence is a finding rather than a skip.
    if raw_expect is None:
        expect = None
        results.append(('duration vs props', 'UNVERIFIABLE',
                        f'{dur:.2f}s (props carry no totalDuration)'))
        print(f'  [UNVERIFIABLE] duration vs props: {dur:.2f}s (props carry no totalDuration)')
        print('       -> the props must state totalDuration. It cannot be derived here:')
        print('          section counts come from the props fields, but per-section')
        print('          durations are TS literals (3 / 2.4 / 5+0.9*items) in report-data.ts.')
    else:
        expect = float(raw_expect)
        # Relative, with a floor of 0.05s and nothing else. An earlier attempt kept
        # `max(0.6, expect * 0.02)`, which is still an absolute tolerance wearing a
        # relative costume: on a 4s clip the 0.6 floor dominates and a 14.75% error
        # sails through, which is the exact defect this replaces. The 0.05s floor
        # exists only to absorb container rounding — the demo render is 718 frames at
        # 24fps = 29.9167s against a declared 29.9s, a 0.056% error — and it is under
        # 1.2 frames. Against that 0.056% the 2% allowance has 35x headroom.
        tolerance = max(0.05, expect * 0.02)
        delta = dur - expect
        rel = abs(delta) / expect * 100 if expect else 0.0
        # +1e-9 so a delta sitting exactly ON the tolerance is decided by the rule
        # rather than by float noise: at exactly 2.00% the two compared as
        # 1.2000000000000002 > 1.2 and a clip inside the stated tolerance failed.
        # Real renders are nowhere near this — the demo is 0.056% against a 2%
        # allowance — but a boundary that floats is a boundary that surprises.
        ok = abs(delta) <= tolerance + 1e-9
        detail = (f'{dur:.2f}s vs {expect:.2f}s — delta {delta:+.2f}s ({rel:+.2f}% relative), '
                  f'tolerance {tolerance:.3f}s')
        check('duration vs props', ok, detail)

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
    unverifiable = [n for n, ok, _ in results if ok == 'UNVERIFIABLE']
    total = len(results)
    verdict = 'FAIL' if fails else ('UNVERIFIABLE' if unverifiable else 'PASS')
    print(f'\n=== RESULT: {verdict} '
          f'({total - len(fails) - len(unverifiable)}/{total} verified'
          + (f', {len(unverifiable)} unverifiable' if unverifiable else '')
          + (f', {len(fails)} failed' if fails else '') + ') ===')
    if unverifiable:
        print(f'    not verifiable: {", ".join(unverifiable)}')
    return 0 if not fails and not unverifiable else 1


if __name__ == '__main__':
    sys.exit(main())
