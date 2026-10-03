"""P23 — `flicker` stays UNAVAILABLE, and the guard knows it.

WHAT THIS GUARDS
----------------
The UNAVAILABLE reason for `flicker` was:

    'needs a luminance time-series instrument across a frame range, which no
     existing render in out/ provides as a sequence.'

P23 measured that sentence and it was FALSE in its second clause:
`out/p13_probe` holds 329 frame PNGs across 9 ordered directories, and they are
real frame sequences. The instrument has a subject. The reason was replaced with
the two blockers that are real and measured — the corpus is strided (stride 20),
so it aliases the entire flicker band to a flat line, and it holds zero
flickering renders, so no cut point can be placed against it.

WHY THIS FILE IS NOT A TEXT ASSERTION
-------------------------------------
This project has been fooled seven times by `assert <phrase> in source`, and the
phrase most vulnerable to that is a REASON STRING — which is exactly what a
previous guard for this rule did (`('flicker', 'time-series')`). That guard was
removed rather than re-worded: it pinned a sentence that is now known to be
false, and pinning a false sentence is worse than pinning nothing.

So every claim below is reached by CALLING the rule and reading its verdict,
`value`, `trusted` and `extra` — the same four facts `unavailable_findings()`
returns, which is the path a consumer reads. Nothing here asserts that a word
appears in `visual_qa.py`.

THE QUESTION THIS FILE MUST ANSWER
----------------------------------
    "IF SOMEONE IMPLEMENTED `flicker` TOMORROW, WOULD THIS SUITE GO RED AND
     ASK FOR THE REASON TO BE UPDATED?"

The answer has to be yes, on the VERDICT and not on the prose. So the guards
below pin:
  * `flicker` currently reports UNAVAILABLE with no number, untrusted;
  * it is reached through the real CLI path, not a private helper;
  * the two MEASURED blockers are carried in `extra` as DATA, so they can be
    re-measured rather than trusted, and so a future implementer has to update
    that data instead of silently replacing it.

The mutations recorded with this work order — flipping the verdict to FAIL and
to PASS — both go red, and the report says on which assertion.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import visual_qa as vqa  # noqa: E402


# ── helpers: read the rule the way a consumer does ───────────────────────────

def _flicker() -> 'vqa.Finding':
    """The `flicker` finding as `unavailable_findings()` publishes it.

    Raises rather than returning None: a rule that stopped being reported is a
    failure of THIS guard, not a skip.
    """
    hits = [f for f in vqa.unavailable_findings() if f.rule == 'flicker']
    if not hits:
        raise AssertionError(
            'flicker is no longer reported by unavailable_findings(). Either it '
            'was implemented (then this file is the record that must be updated '
            'and rewritten) or it was dropped (then the Motion layer lost a '
            'placeholder without anyone deciding to).')
    assert len(hits) == 1, f'flicker reported {len(hits)} times: {hits}'
    return hits[0]


def _run_cli(argv, capsys):
    code = vqa.main([str(a) for a in argv])
    out, err = capsys.readouterr()
    findings = json.loads(out) if '--json' in argv else []
    return code, findings, out, err


# ── 1. the verdict itself ────────────────────────────────────────────────────

def test_flicker_reports_unavailable_with_no_number():
    """The three facts `unavailable_findings()` guarantees for a missing rule.

    `value is None` is the load-bearing one: a number here would be a threshold
    that had been invented rather than measured, which is the whole defect class
    this file exists to keep out.
    """
    f = _flicker()
    assert f.verdict == vqa.UNAVAILABLE, (
        f'flicker reports {f.verdict}, not UNAVAILABLE. If it now decides, it '
        f'needs a measured threshold AND this guard has to be rewritten: '
        f'{f.detail}')
    assert f.value is None, (
        f'flicker carries a number ({f.value!r}) without a measured threshold '
        f'against which to place it')
    assert not f.trusted, (
        'an UNAVAILABLE finding is by definition untrusted; a trusted one would '
        'claim the instrument ran')


def test_flicker_is_reached_through_the_public_path_not_a_private_helper(
        tmp_path, capsys):
    """It must be published by `unavailable_findings()` AND by `--frame`.

    A rule that exists in `UNIMPLEMENTED` but is not emitted by a real run is
    the P21 defect (a path that cannot tell a right input from a wrong one):
    the map would keep the name while every report went quiet.
    """
    assert 'flicker' in vqa.UNIMPLEMENTED, (
        'flicker left UNIMPLEMENTED with no replacement — either it now has a '
        'verdict (with a threshold to justify it) or it belongs there')

    from PIL import Image
    import numpy as np

    a = np.zeros((120, 320, 3), dtype=int) + np.array(
        vqa.THEMES['premium-dark']['bg'])
    a[50:70, 80:120] = np.array(vqa.THEMES['premium-dark']['ink'])
    frame = tmp_path / 'f.png'
    Image.fromarray(a.astype('uint8')).save(frame)

    code, findings, out, _err = _run_cli(['--frame', frame, '--json'], capsys)

    hit = [f for f in findings if f['rule'] == 'flicker']
    assert len(hit) == 1, (
        f'a real --frame run did not emit exactly one flicker finding: {out[:400]}')
    assert hit[0]['verdict'] == vqa.UNAVAILABLE, hit[0]
    assert hit[0]['value'] is None, hit[0]
    # UNAVAILABLE must not reach the exit code: an instrument that was never
    # built is not a failed measurement, so a clean frame is still exit 0 on
    # this rule's account.
    assert all(f['verdict'] != 'FAIL' for f in hit), hit


# ── 2. the measured blockers are DATA, so they can be re-checked ─────────────

def test_the_two_blockers_are_carried_as_measurable_data():
    """The reason's numbers live in `extra`, not only in prose.

    This is what lets a guard disagree with the measurement later. A number
    written only inside a comment decays into folklore; a number in `extra` is
    something a test can compare against a fresh measurement.
    """
    f = _flicker()
    data = f.extra
    assert data, (
        'flicker carries no extra data. The P23 reason quotes measured numbers '
        '— the temporal stride, the aliasing floor, the statistic distribution — '
        'and they must be reachable as data so a later change can be checked '
        'against a fresh measurement rather than believed.')

    for key in ('temporal_stride_frames', 'alias_limit_hz', 'statistic'):
        assert key in data, (
            f'flicker reason no longer carries {key!r}; a measured claim that is '
            f'only prose cannot be re-checked. Keys present: {sorted(data)}')

    stride = data['temporal_stride_frames']
    assert isinstance(stride, dict) and stride, data['temporal_stride_frames']
    assert set(stride) >= {'full_a', 's1'}, (
        f'the stride measurement must name the directories it was measured on: '
        f'{stride}')
    for d, s in stride.items():
        assert isinstance(s, int) and s >= 2, (
            f'{d}: stride {s}. The corpus is strided; a stride of 1 would mean '
            f'contiguous frames were measured and the reason is out of date: '
            f'{stride}')

    hz = data['alias_limit_hz']
    assert isinstance(hz, (int, float)) and 0 < hz < 3.0, (
        f'alias limit {hz} Hz. Stride 20 at 60fps blinds everything faster than '
        f'1.50 Hz; if this number moved, either the measurement or the '
        f'corpus changed and the reason must be re-derived.')

    st = data['statistic']
    for key in ('name', 'n_samples', 'n_segments', 'p5', 'p50', 'p95', 'max'):
        assert key in st, f'statistic is missing {key!r}: {st}'
    assert st['n_samples'] > 0 and st['n_segments'] > 0, st
    assert st['p5'] <= st['p50'] <= st['p95'] <= st['max'], (
        f'percentiles out of order, so the recorded distribution is not a '
        f'distribution: {st}')
    assert 'L[n+1]' in st['name'] or '2' in st['name'], (
        f'the statistic must be named so the formula is reproducible: {st}')


def test_the_recorded_distribution_matches_the_corpus_when_the_corpus_exists():
    """Re-derive the statistic from `out/` and compare to what the reason claims.

    This is the guard that keeps the reason from decaying into folklore. It is
    SKIPPED, not faked, when the gitignored corpus is absent — the P20 pattern,
    and this project's accepted handling.
    """
    probe = ROOT / 'out' / 'p13_probe'
    if not probe.is_dir():
        import pytest
        pytest.skip('out/p13_probe not present (gitignored corpus); the '
                    'distribution in the reason cannot be re-derived here')

    import numpy as np
    weights = np.array((0.2126, 0.7152, 0.0722))

    def mean_luma(p: Path) -> float:
        a = np.asarray(vqa.Image.open(p).convert('RGB')).astype(np.float64) / 255.0
        lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        return float((lin @ weights).mean())

    # The recorded distribution is over the WHOLE corpus, so it is re-derived
    # over the whole corpus. Deriving it from one directory and comparing to a
    # corpus-wide number would fail for the wrong reason and teach nothing.
    dirs = sorted(d for d in probe.iterdir()
                  if d.is_dir() and len(list(d.glob('*.png'))) >= 5)
    if not dirs:
        import pytest
        pytest.skip('out/p13_probe holds no directory of >= 5 frames')

    chunks, nseg = [], 0
    for d in dirs:
        files = sorted(d.glob('*.png'))
        s = np.array([mean_luma(f) for f in files])
        spread = s.max() - s.min() + 1e-12
        cuts = list(np.where(np.abs(np.diff(s)) > 0.8 * spread)[0] + 1)
        bounds = [0] + cuts + [len(s)]
        for i in range(len(bounds) - 1):
            seg = s[bounds[i]:bounds[i + 1]]
            if len(seg) >= 5:
                nseg += 1
                chunks.append(np.abs(np.diff(seg / (seg.max() - seg.min() + 1e-12), 2)))
    if not chunks:
        import pytest
        pytest.skip('no scene-segment of >= 5 samples in the corpus')
    a = np.concatenate(chunks)

    recorded = _flicker().extra['statistic']
    assert len(a) == recorded['n_samples'], (
        f'the reason claims {recorded["n_samples"]} interior samples but the '
        f'corpus now yields {len(a)} over {len(dirs)} directories — the corpus '
        f'or the method changed, so the reason is stale')
    assert nseg == recorded['n_segments'], (
        f'scene-segment count disagrees: reason says {recorded["n_segments"]}, '
        f'corpus gives {nseg}')

    for key, got in (('p5', 5), ('p50', 50), ('p95', 95)):
        mine = float(np.percentile(a, got))
        assert abs(mine - recorded[key]) < 1e-6, (
            f'p{got} disagrees: reason says {recorded[key]}, corpus gives {mine:.6f}')
    assert abs(float(a.max()) - recorded['max']) < 1e-6, (
        f"max disagrees: reason says {recorded['max']}, corpus gives {a.max():.6f}")

    share = float(np.mean(a < 0.10 * a.max()) * 100)
    assert abs(share / 100 - recorded['mass_in_lowest_tenth']) < 0.01, (
        f'mass in the lowest tenth disagrees: reason says '
        f'{recorded["mass_in_lowest_tenth"]}, corpus gives {share / 100:.3f}')


def test_the_stride_is_measured_not_asserted_and_the_reason_says_which_directories():
    """The stride claim names its evidence.

    `full_a` is the directory P23 matched byte-for-byte against its own render,
    so it is the one the stride number rests on; `s1` is the coarser 40-frame
    case that makes the aliasing worse. Naming them is what stops the claim
    from becoming "the corpus is strided" with no referent.
    """
    data = _flicker().extra
    assert data['temporal_stride_frames']['full_a'] == 20, (
        'full_a was measured at video frames 0,20,...,800 (41/41 byte-identical '
        'against demo1.mp4). If that changed, re-derive it — do not edit the '
        f"number: {data['temporal_stride_frames']}")
    assert data['temporal_stride_frames']['s1'] == 40, (
        's1 was measured at video frames 0,40,...,800 (21/21 byte-identical): '
        f"{data['temporal_stride_frames']}")


def test_no_positive_class_is_recorded_as_a_fact_not_prose():
    """Blocker (b) is that the corpus holds no defective render.

    Recorded as a count so it is falsifiable: when someone adds a flickering
    render to `out/`, this number must change and the reason must be rewritten.
    """
    data = _flicker().extra
    assert 'n_flickering_frames_in_corpus' in data, (
        'the second blocker is that no positive class exists; it must be '
        f'recorded as a count so adding one is visible. Keys: {sorted(data)}')
    assert data['n_flickering_frames_in_corpus'] == 0, (
        f"the reason says the corpus holds "
        f"{data['n_flickering_frames_in_corpus']} flickering frames. If that is "
        'now nonzero, a positive class exists and this rule may be decidable — '
        're-derive the threshold instead of editing the number.')


def test_what_would_make_it_available_is_recorded_not_prose():
    """The unlock condition is data, so a future implementer can check it."""
    data = _flicker().extra
    need = data.get('requires', [])
    assert need, (
        'the reason must record what would make the rule available, so the next '
        f'person does not have to guess. Keys: {sorted(data)}')
    joined = ' '.join(str(x).lower() for x in need)
    assert 'contiguous' in joined or 'stride' in joined, (
        f'the unlock condition must name contiguous sampling, which is the '
        f'first measured blocker: {need}')
    assert 'positive' in joined or 'excursion' in joined, (
        f'the unlock condition must name the positive class, which is the '
        f'second measured blocker: {need}')


# ── 3. the verdict must be re-derivable through main(), not only the map ─────

def test_the_json_report_carries_the_verdict_and_the_data(tmp_path, capsys):
    """A machine consumer gets the same facts a human does.

    `detail` is prose and may be reworded; `verdict`, `value` and `extra` are
    the contract. This is what the guard reads, so a mutation that only changed
    the prose would NOT be caught here — which is correct, because prose is not
    the claim.
    """
    from PIL import Image
    import numpy as np

    a = np.zeros((120, 320, 3), dtype=int) + np.array(
        vqa.THEMES['premium-dark']['bg'])
    a[50:70, 80:120] = np.array(vqa.THEMES['premium-dark']['ink'])
    frame = tmp_path / 'f.png'
    Image.fromarray(a.astype('uint8')).save(frame)

    code, findings, out, _err = _run_cli(['--frame', frame, '--json'], capsys)
    hit = next(f for f in findings if f['rule'] == 'flicker')
    assert hit['verdict'] == vqa.UNAVAILABLE
    assert hit['value'] is None
    assert hit['extra']['statistic']['n_samples'] > 0, (
        f'the JSON report dropped the measured data: {hit["extra"]}')
    assert isinstance(code, int)


def test_the_text_report_names_the_rule_so_a_human_sees_it(capsys):
    """The non-JSON path must not silently drop the finding.

    Both report modes are real: CI reads JSON, a person reads the table. A rule
    that appears in one and not the other is the same defect class as P21's.
    """
    code = vqa.main(['--theme-contrast'])
    out, _err = capsys.readouterr()
    assert 'flicker' in out, (
        f'the text report does not mention flicker at all:\n{out[:600]}')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))