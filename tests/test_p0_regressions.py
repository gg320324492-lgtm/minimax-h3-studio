"""Minimal regression net for the P0 production-behaviour changes (review item 1).

Why this exists: P0 changed four production behaviours (fallback default,
polling deadline, PATH injection, fit semantics) and the ONLY verification was
a human running qa_final 16/16 by hand. P1-P18 keep mutating production code,
so these need an automated floor before the next phase starts.

All three subjects are pure functions / cheap filesystem checks — no GPU, no
network, no ComfyUI, seconds to run.

Run:
  python -m pytest tests/ -q
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Portable: derive from this file so a clone can live anywhere on disk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ceo_mindread_ep01' / 'scripts'))
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))


# ── R3: ComfyUI output resolution must fail closed ──────────────────────────

def test_resolve_output_file_defaults_to_strict():
    """The mtime guess must be opt-in. Regression: it used to default True,
    which is how a wrong take could be shipped silently into the edit."""
    import comfy_utils

    sig = __import__('inspect').signature(comfy_utils.resolve_output_file)
    assert sig.parameters['fallback_newest'].default is False, (
        'comfy_utils.resolve_output_file must default to strict (history-only) '
        'resolution; a True default reintroduces the silent-mtime bug (R3)')


def test_resolve_output_file_uses_history_when_present(tmp_path):
    import comfy_utils

    made = tmp_path / 'from_history.mp4'
    made.write_bytes(b'x')
    # history shape: rec['outputs'][<node_id>]['videos'][i]['filename']
    rec = {'outputs': {'136': {'videos': [
        {'filename': 'from_history.mp4', 'subfolder': '', 'type': 'output'}]}}}
    got = comfy_utils.resolve_output_file(rec, output_dir=tmp_path)
    assert got is not None and got.name == 'from_history.mp4'


def test_resolve_output_file_returns_none_without_history(tmp_path):
    """No history entry and no opt-in => None (caller fails), never a guess."""
    import comfy_utils

    decoy = tmp_path / 'MiniMax_H3_decoy.mp4'
    decoy.write_bytes(b'x')
    assert comfy_utils.resolve_output_file({}, output_dir=tmp_path) is None, (
        'strict mode must return None, not the newest file on disk')


def test_resolve_output_file_opt_in_still_works(tmp_path):
    """The escape hatch for interactive/experimental use must keep working."""
    import comfy_utils

    real = tmp_path / 'MiniMax_H3_real.mp4'
    real.write_bytes(b'x')
    got = comfy_utils.resolve_output_file({}, output_dir=tmp_path, fallback_newest=True)
    assert got is not None and got.name == 'MiniMax_H3_real.mp4'


# ── R3: polling must be bounded ────────────────────────────────────────────

def test_wait_for_prompt_has_default_deadline():
    import comfy_utils

    assert isinstance(comfy_utils.DEFAULT_DEADLINE_S, int)
    assert 60 <= comfy_utils.DEFAULT_DEADLINE_S <= 14400
    assert 'deadline_s' in __import__('inspect').signature(comfy_utils.wait_for_prompt).parameters


def test_wait_for_prompt_times_out():
    """A ComfyUI that never answers must terminate, not hang forever."""
    import comfy_utils

    calls = {'n': 0}

    def fake_api(_path):
        calls['n'] += 1
        return {}  # never contains the pid

    assert comfy_utils.wait_for_prompt(fake_api, 'pid-x', deadline_s=0,
                                       log=lambda *_: None, sleep_s=0) is None
    assert calls['n'] >= 1


def test_wait_for_prompt_returns_record_on_completion():
    import comfy_utils

    rec = {'status': {'completed': True}, 'outputs': {}}
    assert comfy_utils.wait_for_prompt(lambda _p: {'p1': rec}, 'p1',
                                       deadline_s=5, log=lambda *_: None,
                                       sleep_s=0) is rec


def test_wait_for_prompt_returns_none_on_job_failure():
    import comfy_utils

    rec = {'status': {'status_str': 'error'}}
    assert comfy_utils.wait_for_prompt(lambda _p: {'p1': rec}, 'p1',
                                       deadline_s=5, log=lambda *_: None,
                                       sleep_s=0) is None


# ── R4: ffmpeg_env must never inject CWD into PATH ────────────────────────

def test_bare_binary_name_does_not_touch_path(tmp_path, monkeypatch):
    """Regression: a bare 'ffmpeg' went through abspath() -> CWD/ffmpeg, whose
    parent (CWD) always exists, so the CWD got prepended to PATH."""
    import ffmpeg_env

    monkeypatch.chdir(tmp_path)
    before = __import__('os').environ.get('PATH', '')
    ffmpeg_env.prepend_to_path('ffmpeg', quiet=True)
    after = __import__('os').environ.get('PATH', '')
    assert after == before, 'bare command name must leave PATH untouched (R4)'
    assert str(tmp_path).lower() not in after.lower().split(';')[0].lower()


def test_real_binary_still_prepends(monkeypatch):
    import os
    from pathlib import Path as _P

    import ffmpeg_env

    real = _P(ffmpeg_env.FFMPEG)
    if not real.exists():
        pytest.skip('bundled ffmpeg not present on this machine')
    os.environ['PATH'] = 'C:\\Windows\\system32'
    ffmpeg_env.prepend_to_path(ffmpeg_env.FFMPEG, quiet=True)
    assert os.environ['PATH'].split(';')[0] == str(real.parent)


# ── R5: fit must not double-stretch mismatched aspect ──────────────────────

def test_emit_props_fit_auto_rule():
    """SR-direct output is already at target geometry (fill is safe); raw clips
    are not (fill would deform them a second time)."""
    ap_src = (ROOT / 'studio' / 'scripts' / 'emit_props.py').read_text(encoding='utf-8')
    assert "fit = 'fill' if args.sr_dir else 'cover'" in ap_src, (
        'emit_props must pick fill only for per-take SR output, cover otherwise')


def test_contain_is_not_silently_accepted_by_schema():
    """emit_props once accepted --fit contain while the zod schema did not,
    so the render would explode. The CLI choice list and the schema enum must agree."""
    schema = (ROOT / 'studio' / 'src' / 'schemas' / 'timeline-v2.ts').read_text(encoding='utf-8')
    assert "z.enum(['cover', 'fill'])" in schema
    cli = (ROOT / 'studio' / 'scripts' / 'emit_props.py').read_text(encoding='utf-8')
    assert "'contain'" not in cli, (
        'CLI still offers --fit contain but the schema rejects it (R5 contract split)')


# ── P1: take ranking must not silently fall back to T01 ────────────────────

def test_select_takes_has_no_t01_default():
    """Source-text guard (cheap). Regex rather than an exact string so flipping
    quote style cannot smuggle the bug back in.

    This is NOT a behavioural test — a real one would build a two-take fixture
    and assert the non-T01 take can win. See BEHAVIOURAL_SUITE below.
    """
    import re

    src = (ROOT / 'ceo_mindread_ep01' / 'scripts' / 'select_takes.py').read_text(encoding='utf-8')
    assert not re.search(r"take\s*=\s*f?['\"]\{shot_id\}_T01['\"]", src), (
        'select_takes still hard-defaults to T01 — TakeRanker must own selection')
    assert 'auto_rank' in src and 'failures' in src, (
        'select_takes must auto-rank and fail closed on a missing take')


def test_take_ranker_is_in_git():
    """Contagion guard: core selection logic must never live only on this machine."""
    import shutil as _sh

    git = _sh.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    tracked = subprocess.run([git, 'ls-files', 'studio/scripts/take_ranker.py',
                              'studio/scripts/rank_takes.py'],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert len(tracked) == 2, f'take ranker not tracked in git: {tracked}'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))


# ── review item 3: manifest must not rot ───────────────────────────────────

def test_manifest_covers_every_experiments_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'mf', ROOT / 'tests' / 'test_manifest_freshness.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0, (
        'pipeline_manifest.yaml is stale: an experiments/ script is unclassified '
        'or a production path is missing. Agents trust this file.')


def test_local_prompts_are_not_tracked():
    """The h3_generation.json holds the real prompts/seeds — it must never be
    committed, while the generator script that reads it must be."""
    import shutil as _sh

    git = _sh.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    out = subprocess.run([git, 'ls-files', 'ceo_mindread_ep01/00_project/h3_generation.json'],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert out == '', 'h3_generation.json (prompts + seeds) must stay local-only'
    src = (ROOT / 'ceo_mindread_ep01' / 'scripts' / 'gen_keyframes_v3.py').read_text(encoding='utf-8')
    assert '<Picture 1>' not in src, (
        'gen_keyframes_v3.py still hardcodes prompts — they belong in the local JSON')
    tracked = subprocess.run([git, 'ls-files', 'ceo_mindread_ep01/scripts/gen_keyframes_v3.py'],
                             cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert tracked, 'gen_keyframes_v3.py must be tracked (P0.3 fix cannot live only on this machine)'
