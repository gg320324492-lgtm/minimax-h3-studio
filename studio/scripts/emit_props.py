"""Generic timeline-v1 → timeline-v2 props emitter for any project (layout validation / staging).

Converts a project's 00_project/timeline.json into DramaVertical/PsaWide/StoryAnimation
props. Clips are hardlinked RAW (no SR) — use for template/layout validation; for
delivery-quality renders run per-take SR first and pass --sr-dir.

Supports titlecard (from titlecard_duration) and endcard (from endcard_start) segments.

Usage (layout validation, raw clips):
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/emit_props.py \
      --project-dir piyao_2026 --template psa-wide --job piyao_check \
      --width 1920 --height 1080
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
STUDIO_PUBLIC = ROOT / 'studio' / 'public'
FPS = 24


def hardlink_into(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        getattr(__import__('os'), 'link')(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-dir', required=True)
    ap.add_argument('--template', required=True,
                    choices=['drama-vertical', 'psa-wide', 'story-animation'])
    ap.add_argument('--job', required=True)
    ap.add_argument('--width', type=int, required=True)
    ap.add_argument('--height', type=int, required=True)
    ap.add_argument('--clip-dir', default='04_video_selected')
    ap.add_argument('--sr-dir', default=None,
                    help='e.g. 04_video_selected_sr — use <SID>_1080.mp4 SR outputs')
    ap.add_argument('--audio', default=None,
                    help='project-relative premixed audio; auto-discovered if omitted')
    args = ap.parse_args()

    proj = ROOT / args.project_dir
    tl = json.loads((proj / '00_project' / 'timeline.json').read_text(encoding='utf-8'))

    audio = args.audio
    if audio is None:
        for cand in sorted((proj / '07_edit').glob('*WITH_AUDIO*.mp4')):
            audio = str(cand.relative_to(proj)).replace('\\', '/')
            break
    if audio is None:
        for cand in sorted((proj / '09_final').glob('*.mp4')):
            audio = str(cand.relative_to(proj)).replace('\\', '/')
            break
    if audio is None:
        print('no premixed audio found (07_edit/*WITH_AUDIO*.mp4 or 09_final/*.mp4)',
              file=sys.stderr)
        return 1

    job_dir = STUDIO_PUBLIC / 'jobs' / args.job
    job_dir.mkdir(parents=True, exist_ok=True)

    shots = []
    for sid in tl['shot_boundaries']:
        name = f'{sid}_1080.mp4' if args.sr_dir else f'{sid}.mp4'
        src = proj / (args.sr_dir or args.clip_dir) / name
        if not src.exists():
            # 回退：piyao/liaozhai 式布局——03_video_raw/<SID>/ 下取第一个 take
            takes = sorted((proj / '03_video_raw' / sid).glob('*.mp4'))
            if not takes:
                print(f'missing clip for {sid}: {src} and no takes in 03_video_raw/{sid}/',
                      file=sys.stderr)
                return 1
            src = takes[0]
            name = src.name
        hardlink_into(src, job_dir / name)
        shots.append({
            'id': sid,
            'file': f'jobs/{args.job}/{name}',
            'trimBefore': 0,
            'durationInFrames': round(tl['shot_boundaries'][sid]['duration'] * FPS),
        })

    props = {
        'version': 2,
        'project': args.project_dir,
        'template': args.template,
        'format': {'width': args.width, 'height': args.height, 'fps': FPS},
        'totalDuration': tl['total_duration'],
        'fit': 'fill',
        'shots': shots,
        'audioBus': {'premixed': f'jobs/{args.job}/PREMIXED{Path(audio).suffix.lower()}'},
        'subtitles': [
            {'id': e['id'], 'text': e['text'], 'style': e['style'],
             'start': e['start'], 'end': e['end']}
            for e in tl['subtitle_events']
        ],
        'overlays': [],
    }
    hardlink_into(proj / audio, job_dir / f'PREMIXED{Path(audio).suffix.lower()}')

    if 'titlecard_duration' in tl:
        props['titlecard'] = {
            'durationInFrames': round(tl['titlecard_duration'] * FPS),
            'lines': [],
            'background': 'black',
        }
    if 'endcard_start' in tl:
        props['endcard'] = {
            'durationInFrames': round((tl['total_duration'] - tl['endcard_start']) * FPS),
            'lines': [],
            'background': 'black',
        }

    out = job_dir / 'props.json'
    out.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding='utf-8')
    total = sum(s['durationInFrames'] for s in shots)
    print(f'props: {out}')
    print(f'{len(shots)} shots, {total} frames ({total / FPS:.1f}s), '
          f'titlecard={"yes" if "titlecard" in props else "no"} '
          f'endcard={"yes" if "endcard" in props else "no"}, audio={audio}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
