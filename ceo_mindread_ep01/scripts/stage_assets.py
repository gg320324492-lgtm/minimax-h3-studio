"""Stage timeline_v2 assets into studio/public/jobs/<job>/ and emit render props.

- Validates timeline_v2 against studio/src/schemas/timeline-v2.schema.json (双端契约).
- Hardlinks (same drive, zero copy) each shot file + premixed audio into the job dir.
- Rewrites asset paths to public/-relative (jobs/<job>/...) and writes props.json.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe ceo_mindread_ep01/scripts/stage_assets.py --job ep01_v3
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
EP01 = ROOT / 'ceo_mindread_ep01'
STUDIO_PUBLIC = ROOT / 'studio' / 'public'
SCHEMA_PATH = ROOT / 'studio' / 'src' / 'schemas' / 'timeline-v2.schema.json'


def hardlink_into(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f'missing asset: {src}')
    if dst.exists():
        dst.unlink()
    try:
        os_link = getattr(__import__('os'), 'link')
        os_link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True, help='job id, becomes studio/public/jobs/<job>/')
    ap.add_argument('--timeline', default='00_project/timeline_v2.json',
                    help='project-relative path to the timeline v2 JSON')
    args = ap.parse_args()

    tl_path = EP01 / args.timeline
    tl = json.loads(tl_path.read_text(encoding='utf-8'))

    try:
        import jsonschema
    except ImportError:
        print('jsonschema not installed in this python; run: '
              'E:/ComfyUI/venv/Scripts/python.exe -m pip install jsonschema', file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    jsonschema.validate(tl, schema)
    print(f'schema OK: {tl_path.name}')

    job_dir = STUDIO_PUBLIC / 'jobs' / args.job
    job_dir.mkdir(parents=True, exist_ok=True)

    props = json.loads(json.dumps(tl))  # deep copy
    for shot in props['shots']:
        src = EP01 / shot['file']
        basename = Path(shot['file']).name
        hardlink_into(src, job_dir / basename)
        shot['file'] = f'jobs/{args.job}/{basename}'

    premixed_src = EP01 / props['audioBus']['premixed']
    premixed_name = 'PREMIXED' + premixed_src.suffix.lower()
    hardlink_into(premixed_src, job_dir / premixed_name)
    props['audioBus']['premixed'] = f'jobs/{args.job}/{premixed_name}'

    props_path = job_dir / 'props.json'
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding='utf-8')

    total_frames = sum(s['durationInFrames'] for s in props['shots'])
    print(f'staged: {len(props["shots"])} shots + 1 audio -> {job_dir}')
    print(f'props: {props_path} ({total_frames} frames, {len(props["subtitles"])} subtitles)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
