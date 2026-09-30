"""Migrate EP01's hardcoded prompts into structured ShotSpecs (P2).

The existing prompts (in h3_generation.json) are prose blobs. This reads them,
proposes a structured breakdown for the two shots that are demonstrably
non-atomic, and writes a ShotSpec file for review.

Human review is REQUIRED: the split of a non-atomic prompt into atomic shots is
a creative decision (where to cut, what each half should show), not something
to guess from the text.

Run:
  E:/ComfyUI/venv/Scripts/python.exe pipeline/migrate_shotspecs.py --project ceo_mindread_ep01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shotspec import ShotSpec, to_dict, validate_atomic  # noqa: E402

ROOT = Path(r'E:\Minimax-H3')

# The two EP01 prompts that ask one generation to contain multiple shots.
# Left empty on purpose: the split is a creative call for a human.
NEEDS_SPLIT: dict[str, str] = {
    'S06': (
        '当前 prompt 是 "Two-shot medium close-up: ... then the camera cuts to ..."。\n'
        '       需要人工决定：拆成几个原子镜头？各自的主体/动作/机位/时长？\n'
        '       拆分后 S06A/S06B 分别生成，剪辑点由 timeline 决定。'
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='ceo_mindread_ep01')
    args = ap.parse_args()

    proj = ROOT / args.project
    gen = json.loads((proj / '00_project' / 'h3_generation.json').read_text(encoding='utf-8'))
    refs = gen.get('refs', {})
    ref_names = list(refs.values())

    out_shots = []
    non_atomic = []
    for sid, s in gen['shots'].items():
        prompt = gen['prompts'].get(s.get('prompt_key', ''), '')
        beats = validate_atomic(prompt)
        if beats:
            non_atomic.append((sid, beats[0]))
        spec = ShotSpec(
            id=sid,
            purpose='',
            duration_target_s=round(s.get('length', 0) / 24.0, 3),
            generation_frames=s.get('length', 0),
            seed_base=s.get('seed_base', 0),
            takes=s.get('takes', 1),
            # prose stays in the source JSON; the spec carries the structure and
            # a pointer, so no prompt text is duplicated into a second file.
            extra={
                'prompt_source': s.get('prompt_key'),
                'migrate_note': NEEDS_SPLIT.get(sid, ''),
            },
        )
        out_shots.append(to_dict(spec))

    payload = {
        '_note': 'ShotSpec 骨架 — 由 migrate_shotspecs.py 生成，需人工补全 subject/action/'
                 'camera 等结构化字段后交给 prompt_compiler.py。',
        '_refs': refs,
        'config': {
            'aspect': '9:16',
            'look': 'cinematic, photorealistic',
            'reference_tokens': {str(i + 1): n.replace('_MASTER_REFERENCE.png', '').lower().replace('_', ' ')
                                for i, n in enumerate(ref_names)},
        },
        'shots': out_shots,
    }
    out = proj / '00_project' / 'shot_specs.json'
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {out} ({len(out_shots)} specs)')
    if non_atomic:
        print(f'\n需要人工拆分的非原子镜头（{len(non_atomic)}）：')
        for sid, why in non_atomic:
            print(f'  ! {sid}: {why}')
        print('\n拆分后重跑本脚本即可得到干净骨架。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
