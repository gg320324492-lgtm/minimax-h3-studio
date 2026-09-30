"""Prompt Compiler (P2) — ShotSpec -> H3 prompt, deterministically.

Contract (master plan §P2 precondition):
  * reads  a gitignored JSON (ShotSpecs)  -> may contain project IP
  * writes a gitignored JSON (compiled)  -> the render-ready prompt set
  * this module contains ZERO project prompt literals; the only strings it owns
    are structural connectives and the fixed H3 style suffix, which live in
    STYLE / SECTION constants below so they can be overridden per project via
    the config JSON rather than by editing code.

Determinism: same ShotSpec + same config => byte-identical prompt. That is what
makes prompt changes reviewable (diff the JSON) and reproducible (recompile).

Usage:
  E:/ComfyUI/venv/Scripts/python.exe pipeline/prompt_compiler.py \
      --specs ceo_mindread_ep01/00_project/shot_specs.json \
      --out   ceo_mindread_ep01/00_project/h3_prompts.compiled.json
"""

from __future__ import annotations

import argparse
import hashlib
import re
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shotspec import ShotSpec, from_dict, to_dict, validate_atomic  # noqa: E402

COMPILER_VERSION = 'p2.1'

# --- structural connectives (not project IP) --------------------------------
# Everything the compiler can emit is assembled from these. Adding a new section
# means adding a key here, never editing a sentence into a script.
SECTION_ORDER = ('subject', 'action', 'environment', 'camera', 'lighting', 'style')

FIELD_TO_SECTION = {
    'subject': 'subject',
    'action': 'action',
    'environment': 'environment',
    'camera': 'camera',
    'lighting': 'lighting',
    'style': 'style',
}

JOIN_WITHIN_SECTION = ', '
JOIN_SECTIONS = '. '

_NEG_PREFIX = re.compile(r'^\s*(?:no|not|without|avoid)\s+', re.IGNORECASE)


def _strip_negation(text: str) -> str:
    """'no text artifacts' -> 'text artifacts' so the compiler can prefix a
    single 'Avoid:' without producing 'Avoid: no ...'."""
    return _NEG_PREFIX.sub('', text.strip()).strip()


def default_config() -> dict:
    return {
        'compiler_version': COMPILER_VERSION,
        'aspect': '9:16',
        'look': 'cinematic, photorealistic',
        'negative': '',
        'reference_tokens': {},   # e.g. {"1": "INTERN_MASTER_REFERENCE.png"}
        'section_order': list(SECTION_ORDER),
    }


def compile_prompt(spec: ShotSpec, config: dict) -> str:
    """Assemble the H3 prompt for one atomic shot."""
    parts: list[str] = []

    # references first: the model binds <Picture N> before it reads prose
    tokens = config.get('reference_tokens', {})
    used = [tok for tok in spec.references if tok in tokens]
    if used:
        binding = ', '.join(f'<Picture {i}> as {tokens[i]}' for i in used)
        parts.append(f'Reference: {binding}')

    if config.get('aspect'):
        parts.append(f'Vertical {config["aspect"]}')
    if config.get('look'):
        parts.append(config['look'])

    for field in config.get('section_order', SECTION_ORDER):
        value = getattr(spec, field, '') if hasattr(spec, field) else ''
        if not value:
            continue
        label = FIELD_TO_SECTION.get(field, field)
        parts.append(f'{label}: {value}')

    negatives = list(spec.negative_constraints) + list(config.get('negative', '').split(';'))
    # Accept both "no X" and plain "X" phrasing; avoid emitting "Avoid: no X".
    negatives = [_strip_negation(n) for n in negatives if n and n.strip()]
    if negatives:
        parts.append('Avoid: ' + '; '.join(negatives))

    return JOIN_SECTIONS.join(parts).strip()


def compile_all(specs: list[ShotSpec], config: dict) -> dict:
    out: dict[str, dict] = {}
    for spec in specs:
        prompt = compile_prompt(spec, config)
        out[spec.id] = {
            'prompt': prompt,
            'generation_frames': spec.generation_frames,
            'seed_base': spec.seed_base,
            'takes': spec.takes,
            'duration_target_s': spec.duration_target_s,
            'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--specs', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--config', type=Path, default=None,
                    help='optional JSON overriding default_config()')
    ap.add_argument('--check', action='store_true',
                    help='validate only; do not write (exit 1 on any problem)')
    args = ap.parse_args()

    raw = json.loads(args.specs.read_text(encoding='utf-8'))
    cfg = default_config()
    if args.config and args.config.exists():
        cfg.update(json.loads(args.config.read_text(encoding='utf-8')))
    if isinstance(raw.get('config'), dict):
        cfg.update(raw['config'])

    specs = [from_dict(d) for d in raw.get('shots', [])]
    problems: list[str] = []
    for s in specs:
        problems += s.validate()
    if problems:
        print(f'{len(problems)} problem(s):')
        for p in problems:
            print(f'  ! {p}')
        return 1

    compiled = compile_all(specs, cfg)
    payload = {
        '_note': 'Compiled by pipeline/prompt_compiler.py — regenerate, do not hand-edit.',
        '_compiler_version': COMPILER_VERSION,
        '_source': args.specs.name,
        '_config': cfg,
        'shots': compiled,
    }
    if not args.check:
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding='utf-8')
        print(f'compiled {len(compiled)} shots -> {args.out}')
        for sid, v in compiled.items():
            print(f'  {sid}: {v["generation_frames"]}f x{v["takes"]} '
                  f'({v["prompt_sha256"]})')
    else:
        print(f'OK — {len(compiled)} specs valid, not writing (--check)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
