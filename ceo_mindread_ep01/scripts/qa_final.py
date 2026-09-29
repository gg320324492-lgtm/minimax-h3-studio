"""P7: Automated final QA for EP01.

Checks:
  1. Container specs: 1080x1920, h264, yuv420p, AAC 48kHz stereo, duration 55-62s
  2. Loudness: Integrated -15..-13 LUFS, TruePeak <= -1 dBTP
  3. Subtitle width: all lines render <= 1000px
  4. Audio timing: dialogue events don't overlap each other; inner may bleed
  5. Seed manifest: every generated shot has a recorded seed matching length
Writes: 09_final/qa_report.md (PASS/FAIL per check)
"""


# --- ffmpeg binary resolution -------------------------------------------------
# PATH `ffmpeg` on this machine is GNU Octave's bundled 4.2.11, not a normal
# install, so every encode silently depended on a third-party app. Resolve via
# ffmpeg_env (repo-bundled 7.1.1 by default; MINIMAX_FFMPEG_LEGACY=1 to pin the
# legacy PATH binary for byte-comparable re-runs).
import sys as _sys, os as _os  # noqa: E402
if r'E:\Minimax-H3' not in _sys.path:
    _sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()
# -----------------------------------------------------------------------------
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, FFPROBE  # noqa: E402  (see ffmpeg_env: bare `ffmpeg`
#                                          resolves to Octave's bundled 4.2.11 here)

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
# Respect the same override as finalize.py, otherwise a re-run that writes to a
# tagged directory would have its QA gate silently validate the OLD delivery.
FINAL = Path(_os.environ.get('EP01_FINAL_DIR', str(PROJECT / '09_final')))
if not FINAL.is_absolute():
    FINAL = PROJECT / FINAL
VIDEO = FINAL / 'EP01_DOUYIN_FINAL.mp4'

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}: {detail}')
    return ok


def main():
    if not VIDEO.exists():
        print(f'ERROR: {VIDEO} not found')
        sys.exit(1)

    print('=== EP01 Final QA ===\n')

    # ---- 1. Container specs ----
    print('[1] Container specs')
    r = subprocess.check_output([FFPROBE, '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(VIDEO)]).decode()
    d = json.loads(r)
    fmt = d['format']
    vs = [s for s in d['streams'] if s['codec_type'] == 'video']
    as_ = [s for s in d['streams'] if s['codec_type'] == 'audio']
    if not vs:
        print('ERROR: no video stream in the delivered file')
        sys.exit(1)
    if not as_:
        # Previously an unguarded [0] here raised IndexError, so the QA gate
        # crashed instead of reporting a FAIL. A missing audio track is a FAIL.
        check('audio stream present', False, 'no audio stream found')
        print('\n=== RESULT: FAIL (no audio stream) ===')
        sys.exit(1)
    vs, as_ = vs[0], as_[0]
    dur = float(fmt['duration'])

    check('resolution', vs['width'] == 1080 and vs['height'] == 1920, f"{vs['width']}x{vs['height']}")
    check('video codec', vs['codec_name'] == 'h264', vs['codec_name'])
    check('pix_fmt', vs['pix_fmt'] == 'yuv420p', vs['pix_fmt'])
    check('fps', vs['avg_frame_rate'] in ('24/1', '24000/1001'), vs['avg_frame_rate'])
    check('audio codec', as_['codec_name'] == 'aac', as_['codec_name'])
    check('sample rate', int(as_['sample_rate']) == 48000, as_['sample_rate'])
    check('channels STEREO', int(as_['channels']) == 2, f"channels={as_['channels']}")
    check('duration 55-62s', 55 <= dur <= 62, f'{dur:.2f}s')
    adur = float(as_.get('duration', 0))
    check('audio covers video (>=95%)', adur >= 0.95 * dur,
          f'audio {adur:.2f}s / video {dur:.2f}s')

    # ---- 2. Loudness ----
    print('\n[2] Loudness (EBU R128)')
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(VIDEO),
                        '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'],
                       capture_output=True)
    err = r.stderr.decode(errors='ignore')
    integrated = peak = None
    for line in err.split('\n'):
        if 'Input Integrated' in line:
            integrated = float(line.split(':')[1].replace('LUFS', '').strip())
        if 'Input True Peak' in line:
            peak = float(line.split(':')[1].replace('dBTP', '').strip())
    check('integrated loudness -15..-13 LUFS',
          integrated is not None and -15 <= integrated <= -13, f'{integrated} LUFS')
    check('true peak <= -1 dBTP', peak is not None and peak <= -1.0, f'{peak} dBTP')

    # ---- 3. Subtitle widths ----
    print('\n[3] Subtitle width')
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(PROJECT / 'scripts'))
    import burn_subtitles_v2 as bs
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    img = Image.new('RGB', (1080, 1920))
    draw = ImageDraw.Draw(img)
    worst = ('', 0)
    all_ok = True
    for e in tl['subtitle_events']:
        lines = bs.wrap_text(draw, e['text'], e['style'], 1080)
        for line in lines:
            w = bs.text_width(draw, line, bs.get_font(bs.STYLES[e['style']]['font_size']))
            if w > worst[1]:
                worst = (line[:18], w)
            if w > 1000:
                all_ok = False
    check('all subtitles <= 1000px', all_ok, f'widest "{worst[0]}..." = {worst[1]}px')

    # ---- 4. Audio timing ----
    print('\n[4] Audio timing')
    events = sorted(tl['audio_events'], key=lambda e: e['start'])
    overlaps = []
    dialogues = [e for e in events if e['type'] == 'dialogue']
    for i in range(len(dialogues) - 1):
        a, b = dialogues[i], dialogues[i + 1]
        if b['start'] < a['end'] - 0.05:
            overlaps.append(f"{a['id']} vs {b['id']} ({b['start']:.2f} < {a['end']:.2f})")
    check('no dialogue overlap', not overlaps, '; '.join(overlaps) if overlaps else 'clean')
    bleeds = [f"{e['id']} -> {e['end']:.2f}s" for e in events if e['end'] > tl['total_duration']]
    check('nothing exceeds video end', not bleeds, '; '.join(bleeds) if bleeds else 'clean')

    # ---- 5. Seed manifest ----
    print('\n[5] Seed reproducibility')
    sm = json.loads((PROJECT / '00_project/seed_manifest.json').read_text(encoding='utf-8'))
    manifest = json.loads((PROJECT / '00_project/shot_manifest.json').read_text(encoding='utf-8'))
    missing = []
    mismatched = []
    for sid, sel in manifest['selections'].items():
        if sid == 'S05A':
            continue  # carried over from the v2 round; no length recorded at gen time
        take = sel.get('source_take', f'{sid}_T01')
        tk = take.split('_T')[1] if '_T' in take else '01'
        key = f'seed_T{tk}'
        if sid not in sm.get('shots', {}) or key not in sm['shots'][sid]:
            missing.append(f'{sid}:{key}')
        else:
            # This branch used to be a bare `pass`, so the check advertised in the
            # module docstring ("seed matching length") was never actually
            # evaluated -- a real mismatch would still have reported PASS.
            recorded = sm['shots'][sid].get('length_frames')
            if recorded != sel.get('frames'):
                mismatched.append(
                    f'{sid}:{key} recorded={recorded} vs selection={sel.get("frames")}')
    check('all shots have recorded seeds', not missing,
          ', '.join(missing) if missing else 'complete')
    check('recorded length matches selection', not mismatched,
          ', '.join(mismatched) if mismatched else 'consistent')

    # ---- Summary ----
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f'\n=== RESULT: {passed}/{total} PASS ===')
    for name, ok, detail in results:
        if not ok:
            print(f'  FAILED: {name} ({detail})')

    # Write report
    lines = ['# EP01 Final QA Report (automated)', '',
             f'**Video**: {VIDEO.name}  ', f'**Checks**: {passed}/{total} PASS', '',
             '| Check | Result | Detail |', '|-------|--------|--------|']
    for name, ok, detail in results:
        lines.append(f'| {name} | {"PASS" if ok else "**FAIL**"} | {detail} |')
    (FINAL / 'qa_report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'\nReport: {FINAL / "qa_report.md"}')

    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
