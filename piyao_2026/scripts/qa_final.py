"""Automated final QA for piyao_2026.

Checks:
  1. container: 1920x1080 h264 yuv420p 24fps, AAC 48kHz stereo, 100-115s
  2. loudness: -15..-13 LUFS integrated, true peak <= -1 dBTP
  3. subtitle widths fit 1920-wide frame
  4. audio timing: narration events never overlap, nothing runs past the end
  5. seeds recorded for every shot, lengths match config
  6. AI label present (persistent corner + end card event in the timeline)
Writes 09_final/qa_report.md; exit 0 only when everything passes.
"""
import json
import subprocess
import sys
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, FFPROBE, prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
VIDEO = PROJECT / '09_final' / '它只是换了一个地名_参赛版_1080P.mp4'
CFG = json.loads((PROJECT / '00_project/shots.json').read_text(encoding='utf-8'))
ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08',
         'S09', 'S10', 'S11', 'S12', 'S13', 'S14']

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}: {detail}')
    return ok


def main():
    if not VIDEO.exists():
        print(f'ERROR: {VIDEO} not found')
        sys.exit(1)
    print('=== piyao_2026 Final QA ===\n')

    r = subprocess.check_output([FFPROBE, '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(VIDEO)]).decode()
    d = json.loads(r)
    fmt = d['format']
    vs = [s for s in d['streams'] if s['codec_type'] == 'video']
    as_ = [s for s in d['streams'] if s['codec_type'] == 'audio']
    if not vs or not as_:
        check('streams present', False, f'video={bool(vs)} audio={bool(as_)}')
        sys.exit(1)
    vs, as_ = vs[0], as_[0]
    dur = float(fmt['duration'])

    print('[1] Container specs')
    check('resolution 1920x1080', (vs['width'], vs['height']) == (1920, 1080),
          f"{vs['width']}x{vs['height']}")
    check('video codec h264', vs['codec_name'] == 'h264', vs['codec_name'])
    check('pix_fmt yuv420p', vs['pix_fmt'] == 'yuv420p', vs['pix_fmt'])
    check('fps 24', vs['avg_frame_rate'] == '24/1', vs['avg_frame_rate'])
    check('audio aac 48k stereo',
          as_['codec_name'] == 'aac' and int(as_['sample_rate']) == 48000
          and int(as_['channels']) == 2,
          f"{as_['codec_name']}/{as_['sample_rate']}/{as_['channels']}ch")
    check('duration 100-115s', 100 <= dur <= 115, f'{dur:.2f}s')
    adur = float(as_.get('duration', 0))
    check('audio covers video (within 0.15s)', adur >= dur - 0.15,
          f'{adur:.2f}s / {dur:.2f}s')

    print('\n[2] Loudness (EBU R128)')
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(VIDEO),
                        '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'],
                       capture_output=True)
    integrated = peak = None
    for line in r.stderr.decode(errors='ignore').split('\n'):
        if 'Input Integrated' in line:
            integrated = float(line.split(':')[1].replace('LUFS', '').strip())
        if 'Input True Peak' in line:
            peak = float(line.split(':')[1].replace('dBTP', '').strip())
    check('integrated -15..-13 LUFS',
          integrated is not None and -15 <= integrated <= -13, f'{integrated} LUFS')
    check('true peak <= -1 dBTP', peak is not None and peak <= -1.0, f'{peak} dBTP')

    print('\n[3] Subtitle widths')
    sys.path.insert(0, str(PROJECT / 'scripts'))
    import burn_subtitles as bs
    from PIL import Image, ImageDraw
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    img = Image.new('RGB', (1920, 1080))
    draw = ImageDraw.Draw(img)
    worst, all_ok = ('', 0), True
    for e in tl['subtitle_events']:
        for ln in bs.wrap_text(draw, e['text'], e['style'], 1920):
            w = bs.text_width(draw, ln, bs.get_font(bs.STYLES[e['style']]['size']))
            box_pad = 2 * (bs.STYLES[e['style']].get('box', ((0, 0, 0, 0), 0, 0, 0))[1] or 0)
            if w + box_pad > worst[1]:
                worst = (ln[:16], w + box_pad)
            if w + box_pad > 1860:
                all_ok = False
    check('all subtitle blocks fit 1920px', all_ok,
          f'widest "{worst[0]}..." = {worst[1]}px')

    print('\n[4] Audio timing')
    events = sorted(tl['audio_events'], key=lambda e: e['start'])
    overlaps = [f"{a['id']} vs {b['id']}" for a, b in zip(events, events[1:])
                if b['start'] < a['end'] - 0.05]
    check('no narration overlap', not overlaps, '; '.join(overlaps) or 'clean')
    bleed = [f"{e['id']} -> {e['end']:.2f}s" for e in events + tl['sfx_events']
             if e['end'] > tl['total_duration'] + 0.05]
    check('nothing exceeds video end', not bleed, '; '.join(bleed) or 'clean')

    print('\n[5] Seed reproducibility')
    sm = json.loads((PROJECT / '00_project/seed_manifest.json').read_text(encoding='utf-8'))
    missing, mismatched = [], []
    for sid in ORDER:
        ent = sm.get('shots', {}).get(sid)
        if not ent or 'seed' not in ent:
            missing.append(sid)
            continue
        if ent['length_frames'] != CFG['shots'][sid]['length']:
            mismatched.append(f"{sid}:{ent['length_frames']}!={CFG['shots'][sid]['length']}")
    check('all shots have recorded seeds', not missing, ', '.join(missing) or 'complete')
    check('recorded lengths match config', not mismatched, ', '.join(mismatched) or 'consistent')

    print('\n[6] Compliance labels')
    subs = ' '.join(e['text'] for e in tl['subtitle_events'])
    check('AI label present (corner)', 'AI技术辅助生成' in subs and
          any(e['style'] == 'corner' for e in tl['subtitle_events']), 'corner disclaimer found')
    check('AI label present (end card)', any(e['style'] == 'end_ai' for e in tl['subtitle_events']),
          'end-card AI label found')
    check('dramatization disclaimer', '情景演绎' in subs, 'found')

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f'\n=== RESULT: {passed}/{total} PASS ===')
    for name, ok, detail in results:
        if not ok:
            print(f'  FAILED: {name} ({detail})')

    lines = ['# piyao_2026 Final QA Report', '',
             f'**Video**: {VIDEO.name}  ', f'**Checks**: {passed}/{total} PASS', '',
             '| Check | Result | Detail |', '|-------|--------|--------|']
    for name, ok, detail in results:
        lines.append(f'| {name} | {"PASS" if ok else "**FAIL**"} | {detail} |')
    (PROJECT / '09_final' / 'qa_report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'\nReport: {PROJECT / "09_final" / "qa_report.md"}')
    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
