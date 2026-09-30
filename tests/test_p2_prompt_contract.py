"""P2 contract tests: prompts stay data, compiler stays code.

Master plan §P2 precondition: the prompt compiler reads a gitignored JSON and
writes a gitignored JSON, while the compiler and the generation scripts hold
ZERO prompt literals. This is the same class of risk the P0 review caught for
gen_keyframes_v3 (core logic living only on one machine, or prompts leaking
into a public repo).

Run:
  python -m pytest tests/test_p2_prompt_contract.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))

import prompt_compiler  # noqa: E402
import shotspec  # noqa: E402


def _git(*args: str) -> str:
    import shutil

    git = shutil.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    return subprocess.run([git, *args], cwd=ROOT, capture_output=True,
                          text=True).stdout


def test_compiler_has_no_project_prompt_literals():
    """The compiler may own structural connectives, not project prose."""
    src = (ROOT / 'pipeline' / 'prompt_compiler.py').read_text(encoding='utf-8')
    # specific enough that ordinary English words cannot false-positive
    for marker in ('<Picture 1> as the female', 'Lin Xiaoyu', 'Gu Yanchuan',
                   'executive office', 'cold half-smile'):
        assert marker.lower() not in src.lower(), (
            f'prompt_compiler.py contains project prose ({marker!r}); prompts belong '
            f'in the gitignored JSON, not in code')


def test_generation_script_has_no_prompt_literals():
    src = (ROOT / 'ceo_mindread_ep01' / 'scripts' / 'gen_keyframes_v3.py').read_text(encoding='utf-8')
    assert '<Picture 1>' not in src, 'generator must load prompts from JSON'


def test_prompt_data_files_are_not_tracked():
    for rel in ('ceo_mindread_ep01/00_project/h3_generation.json',
                'ceo_mindread_ep01/00_project/shot_specs.json'):
        assert _git('ls-files', rel).strip() == '', (
            f'{rel} holds project prompts and must stay local-only')


def test_pipeline_modules_are_tracked():
    """Core production logic must be in git, not only on this machine."""
    tracked = _git('ls-files', 'pipeline/').split()
    assert len(tracked) >= 2, f'pipeline/ not tracked: {tracked}'


def test_shotspec_rejects_non_atomic_prompts():
    for bad in ('Wide establishing, cut to the reaction',
                'Two-shot: wide then close-up on her face',
                '镜头切到她的手'):
        assert shotspec.validate_atomic(bad), f'missed non-atomic: {bad!r}'
    for good in ('she hands over the report, then his eyes shift to her',
                 'a slow push in on a trembling hand',
                 'Two-shot medium close-up, both subjects framed together'):
        assert not shotspec.validate_atomic(good), f'false positive on: {good!r}'


def test_shotspec_validates_the_frame_grid():
    for good in (22, 56, 124, 141, 226):
        assert not shotspec.ShotSpec(id='S01', generation_frames=good).validate(), (
            f'{good} is on the 17k+5 grid but was rejected')
    for bad in (100, 55, 60, 130):
        assert shotspec.ShotSpec(id='S01', generation_frames=bad).validate(), (
            f'{bad} violates 17k+5 but passed')


def test_compiler_is_deterministic():
    spec = shotspec.ShotSpec(
        id='S01', subject='a subject', action='does one thing',
        environment='a room', camera='medium shot', generation_frames=124)
    cfg = prompt_compiler.default_config()
    a = prompt_compiler.compile_prompt(spec, cfg)
    b = prompt_compiler.compile_prompt(spec, cfg)
    assert a == b, 'same spec must compile to a byte-identical prompt'
    assert 'does one thing' in a


def test_negative_constraints_are_not_doubled():
    spec = shotspec.ShotSpec(id='S01', action='x', negative_constraints=['no text artifacts'])
    out = prompt_compiler.compile_prompt(spec, prompt_compiler.default_config())
    assert 'Avoid: text artifacts' in out, out
    assert 'Avoid: no ' not in out, f'negation doubled: {out}'


def test_compile_end_to_end_writes_expected_shape():
    spec = shotspec.ShotSpec(id='SX', action='walks to the window',
                             generation_frames=141, seed_base=42, takes=3)
    out = prompt_compiler.compile_all([spec], prompt_compiler.default_config())
    entry = out['SX']
    assert set(entry) >= {'prompt', 'generation_frames', 'seed_base', 'takes',
                          'prompt_sha256'}
    assert entry['takes'] == 3 and entry['generation_frames'] == 141
    assert 'walks to the window' in entry['prompt']


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
