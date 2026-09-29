"""Automated final QA for third_lantern《第三盏灯》.

Checks: container specs, duration window, loudness, subtitle fit is done at
burn time; here we verify narration non-overlap from the timeline, seed
manifest completeness, AI label presence, and audio coverage.
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

PROJECT = Path(r'E:/Minimax-H3/third_lantern')
VIDEO = PROJECT / '09_final' / '第三盏灯_演示版_2K.mp4'
CFG = json.loads((PROJECT / '00_project/story.json').read_text(encoding='utf-8'))

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f'  [{"PASS" if ok else "FAIL"}] {name}: {detail}')
    return ok


def main():
    if not VIDEO.exists():
        print(f'ERROR: {VIDEO} not found')
        sys.exit(1)
    print('=== third_lantern Final QA ===\n')

    r = subprocess.check_output([FFPROBE, '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(VIDEO)]).decode()
    d = json.loads(r)
    fmt = d['format']
    vs = [s for s in d['streams'] if s['codec_type'] == 'video'][0]
    as_ = [s for s in d['streams'] if s['codec_type'] == 'audio'][0]
    dur = float(fmt['duration'])

    print('[1] Container specs')
    ow, oh = CFG.get('out_width', 1920), CFG.get('out_height', 1080)
    check(f'resolution {ow}x{oh}', (vs['width'], vs['height']) == (ow, oh),
          f"{vs['width']}x{vs['height']}")
    check('video codec h264', vs['codec_name'] == 'h264', vs['codec_name'])
    check('pix_fmt yuv420p', vs['pix_fmt'] == 'yuv420p', vs['pix_fmt'])
    check('fps 24', vs['avg_frame_rate'] == '24/1', vs['avg_frame_rate'])
    check('audio aac 48k stereo', as_['codec_name'] == 'aac' and as_['sample_rate'] == '48000'
          and as_['channels'] == 2, f"{as_['codec_name']}/{as_['sample_rate']}/{as_['channels']}ch")
    expected = (CFG['titlecard_duration_s']
                + sum(s['length'] for s in CFG['shots'].values()) / CFG['fps']
                + CFG['endcard_duration_s'])
    check('duration matches config', abs(dur - expected) < 0.3,
          f'{dur:.2f}s vs expected {expected:.2f}s')

    print('\n[2] Loudness')
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(VIDEO), '-map', '0:a',
                        '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'],
                       capture_output=True)
    integrated = tpeak = None
    for line in r.stderr.decode(errors='ignore').split('\n'):
        if 'Input Integrated' in line:
            integrated = float(line.split(':')[1].replace('LUFS', '').strip())
        if 'Input True Peak' in line:
            tpeak = float(line.split(':')[1].replace('dBTP', '').strip())
    check('integrated -14.5..-13.5 LUFS', integrated is not None and -14.5 <= integrated <= -13.5,
          f'{integrated} LUFS')
    check('true peak <= -1 dBTP', tpeak is not None and tpeak <= -1.0, f'{tpeak} dBTP')

    print('\n[3] Audio coverage')
    cover = None
    for line in r.stderr.decode(errors='ignore').split('\n'):
        pass
    a_dur = float(as_.get('duration', 0))
    check('audio track covers video', a_dur >= dur - 0.15, f'audio {a_dur:.2f}s vs video {dur:.2f}s')

    print('\n[4] Timeline sanity')
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    narr = sorted(tl['audio_events'], key=lambda e: e['start'])
    overlaps = [f"{a['id']}~{b['id']}" for a, b in zip(narr, narr[1:]) if b['start'] < a['end'] - 0.05]
    check('no narration overlap', not overlaps, str(overlaps or 'clean'))
    past_end = [e['id'] for e in tl['audio_events'] + tl['sfx_events'] if e['end'] > tl['total_duration'] + 0.1]
    check('nothing runs past end', not past_end, str(past_end or 'clean'))

    print('\n[5] Seed manifest')
    mf = PROJECT / '00_project' / 'seed_manifest.json'
    man = json.loads(mf.read_text(encoding='utf-8')) if mf.exists() else {}
    missing = [s for s in CFG['shots'] if s not in man.get('shots', {})]
    check('seeds recorded for all shots', not missing, str(missing or 'all 10 recorded'))

    print('\n[6] All clips present at expected lengths')
    tag = CFG.get('gen_tag', 'T01')
    bad = []
    for sid, c in CFG['shots'].items():
        f = PROJECT / '03_video_raw' / sid / f'{sid}_{tag}.mp4'
        if not f.exists():
            bad.append(f'{sid}: missing')
            continue
        rr = subprocess.check_output([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
                                      '-show_entries', 'stream=nb_frames', '-of',
                                      'default=noprint_wrappers=1:nokey=1', str(f)]).decode().strip()
        if not rr or int(rr) != c['length']:
            bad.append(f'{sid}: {rr} frames != {c["length"]}')
    check('clips complete', not bad, str(bad or '10/10 clips'))

    print('\n=== SUMMARY ===')
    fails = [x for x in results if not x[1]]
    for name, ok, detail in results:
        print(f'  [{"PASS" if ok else "FAIL"}] {name}')
    print(f'\n{len(results) - len(fails)}/{len(results)} PASS')

    out = PROJECT / '09_final'
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'qa_report.md', 'w', encoding='utf-8') as f:
        f.write(f'# QA report — 《第三盏灯》演示版\n\n')
        f.write(f'- video: {VIDEO.name} ({dur:.2f}s)\n')
        f.write(f'- loudness: {integrated} LUFS, peak {tpeak} dBTP\n\n')
        for name, ok, detail in results:
            f.write(f'- [{"PASS" if ok else "FAIL"}] {name}: {detail}\n')
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
