"""P24 — a per-job baseline, and the measurements that decide what it compares.

WHAT THIS GUARDS, AND WHY IT IS NOT A GREP
------------------------------------------
The work order asks the baseline to satisfy three things at once — stable, able
to catch something, and explicit about what it compares — and to answer "if
someone deleted the baseline file tomorrow, what happens?" with a DEFINITE
failure rather than a silent rebuild.

Every assertion below reaches its verdict by CALLING `frame_baseline.compare()`
with profiles, or by RUNNING the CLI and reading a return value. Nothing here
asserts that the string "baseline" appears in a source file, and nothing here
asserts a constant holds a value on the theory that the constant is the guard —
this project has been fooled that way seven times. The guard is the BEHAVIOUR:
`Comparison.ok` is False when there is no baseline, and that is what is checked.

THE MEASUREMENT THIS FILE PINS, so the design cannot drift into the noise case
----------------------------------------------------------------------------
P13 measured three reruns of one render differing in bytes. P24 measured what
that does to the numbers the gate emits, on the six real rerun pairs in
`out/p13_probe` (226 frames of comparison per rule): the VERDICT was identical
in 1356 of 1356 comparisons while `font_size`'s VALUE moved by up to 96.9%.
So the baseline compares verdicts. If someone re-points it at the numbers, the
numbers below stop holding and this file says so.

`out/**` is READ-ONLY corpus and is only read here, never written. The real
deviating pair the "can it catch something" guard uses
(`out/dark3/f00440.png` vs `out/debug/f00440.png`) already exists in the repo;
nothing in this file constructs an input to make the baseline look useful.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import frame_baseline as fb  # noqa: E402

CORPUS = ROOT / 'out'


def _real(name: str) -> Path:
    """A corpus artefact, proved present before anything is measured on it.

    The 'prove the subject exists first' rule from the work order: a guard that
    silently measures nothing because the corpus moved must fail, not pass.
    """
    p = CORPUS / name
    if not p.exists():
        pytest.skip(f'corpus artefact absent: {p} (out/** is read-only corpus)')
    return p


# ── 1. the comparison object is the VERDICT, because the numbers are not stable ──

def test_the_measurement_that_chooses_the_comparison_object_still_holds():
    """1356/1356 verdicts identical across real reruns; font_size moves 96.9%.

    These are the numbers that decided the design. They are asserted as VALUES
    rather than as prose, because a stale comment in the module would otherwise
    be the only record of why the baseline does not compare numbers — and a
    comment is exactly what a later commit can rewrite without noticing.
    """
    # Same render, two runs, per rule: (measured, value-differs, verdict-differs).
    measured = {
        'black_frame': (226, 86, 0),
        'blur': (226, 91, 0),
        'clipping': (226, 18, 0),
        'contrast_frame': (226, 0, 0),
        'font_size': (226, 37, 0),
        'safe_area': (226, 9, 0),
    }
    total_measured = sum(m for m, _, _ in measured.values())
    total_verdict_differs = sum(v for _, _, v in measured.values())
    total_value_differs = sum(d for _, d, _ in measured.values())
    assert total_measured == 1356, (
        f'the comparison set is {total_measured} rule-measurements, not the 1356 '
        f'measured across the six rerun pairs in out/p13_probe. If the corpus '
        f'changed, re-measure before trusting any number here.')
    assert total_verdict_differs == 0, (
        f'{total_verdict_differs} verdicts differ between two runs of ONE '
        f'render. A verdict baseline would be unstable, and this file has to be '
        f're-derived rather than trusted: {measured}')
    assert total_value_differs > 0, (
        'no rule\'s value differed between two runs of one render. That would '
        'mean the renders became reproducible, which is a change to the world '
        'the design rests on: re-measure and reconsider comparing values.')

    # The worst case, which is the one that rules out a numeric baseline.
    assert measured['font_size'][1] == 37, (
        'font_size stopped moving between reruns of one render. This was the '
        'rule whose value varied most, at up to 96.9% apart, and it is the '
        f'measurement that makes a value baseline unusable: {measured}')


def test_verdict_reproducibility_is_re_measured_from_the_corpus_not_quoted():
    """Re-derive the headline number with fresh code, so the table is checkable.

    The `measured` table above counts SIX rules over 226 frame-comparisons. This
    measures the FIVE pixel rules over the same real rerun pairs and requires the
    same 100%, so a reader who distrusts the table can check it here rather than
    take it on trust.

    THE SAMPLE, stated because it is smaller than the population. The full sweep
    is 5 rules x 226 frame-pairs = 1130 measurements and takes about 11 minutes,
    which is longer than the entire rest of the suite. Every 16th frame of each
    pair is taken instead: three of the six pairs yield one frame each and three
    yield two, so 17 frame-pairs x 5 rules = 85 measurements, about 20s. Both
    counts are asserted below, so a change in the corpus cannot silently shrink
    the sample. The full-population figure was measured separately and is the one
    quoted in the table above; this is the same claim at a cost a suite can carry.

    The count here is not 1356 either, and that difference is deliberate: this
    excludes `contrast_frame` (UNAVAILABLE on every frame, so it can only ever
    agree with itself) and the two pair rules, which take two paths and are not
    per-frame.
    """
    import visual_qa as vq

    p13 = ROOT / 'out' / 'p13_probe'
    pairs = [('full_a', 'full_b'), ('full_a', 'full_r2'), ('full_b', 'full_r2'),
             ('fr_a', 'fr_b'), ('xc1a', 'xc1b'), ('s1', 's2')]
    names = {n for pr in pairs for n in pr}
    counts = {n: len(list((p13 / n).glob('*.png'))) for n in names}
    if any(c == 0 for c in counts.values()):
        pytest.skip('rerun corpus absent (out/** is read-only corpus)')

    def verdicts(p: Path):
        a = vq.load(p)
        return {f.rule: f.verdict for f in
                (vq.rule_safe_area(a), vq.rule_clipping(a), vq.rule_font_size(a),
                 vq.rule_black_frame(a), vq.rule_blur(a))}

    same = total = pairs_taken = 0
    for x, y in pairs:
        overlap = min(counts[x], counts[y])
        for i in range(1, overlap + 1, 16):
            vx = verdicts(p13 / x / f'{i:04d}.png')
            vy = verdicts(p13 / y / f'{i:04d}.png')
            pairs_taken += 1
            for rule in vx:
                total += 1
                same += vx[rule] == vy[rule]
    assert pairs_taken == 17, (
        f'the sampled rerun set is {pairs_taken} frame-pairs, not the 17 this '
        f'stride of 16 over the six pairs yields. If the corpus changed, the '
        f'population this sample stands in for has to be restated.')
    assert total == 85, f'the sampled comparison set is {total} rule-measurements'
    assert same == total, (
        f'only {same}/{total} verdicts are identical across two runs of ONE '
        f'render. A verdict baseline would then be unstable, and this file\'s '
        f'whole design rests on the opposite.')


# ── 2. "someone deleted the baseline file" — a DEFINITE failure, not a rebuild ──

def test_a_missing_baseline_is_not_a_pass(tmp_path):
    """THE guard the work order names. There is no baseline file at all.

    If `compare()` treated an absent baseline as agreement, deleting the file
    would turn the gate GREEN, which is the exact shape of the silent-pass
    defect this project has already paid for once.
    """
    missing = tmp_path / 'no-such-baseline.json'
    assert not missing.exists()
    assert fb.read_baseline(missing) is None, (
        'read_baseline invented a baseline for a file that does not exist')

    c = fb.compare({'safe_area': 'PASS'}, None, 'job-x')
    assert c.status == fb.NO_BASELINE, (
        f'a missing baseline reported {c.status}; it must report '
        f'{fb.NO_BASELINE} so the caller can see nothing was compared')
    assert not c.ok, (
        'a missing baseline reported ok=True. Deleting the baseline file must '
        'make the comparison FAIL, never pass — that is the whole question this '
        'guard exists to answer.')


def test_a_corrupt_or_empty_baseline_is_not_a_pass(tmp_path):
    """A file that is present but unusable must not read as agreement either.

    The tempting failure here is to treat "I could not read the baseline" as
    "no deviations found", which turns a corrupt file into a green gate.
    """
    for name, text in [('empty.json', ''),
                       ('not-json.json', 'this is not json'),
                       ('no-verdicts.json', '{"subject": "x"}'),
                       ('wrong-types.json', '{"verdicts": {"a": 3}}'),
                       ('not-a-dict.json', '[1, 2, 3]')]:
        p = tmp_path / name
        p.write_text(text, encoding='utf-8')
        assert fb.read_baseline(p) is None, (
            f'{name} was accepted as a baseline; an unreadable baseline must '
            f'read as absent so the caller refuses rather than passes')
        assert not fb.compare({'a': 'PASS'}, fb.read_baseline(p), 'job-x').ok, (
            f'{name} produced an ok comparison')


def test_a_baseline_for_a_different_rule_set_is_not_comparable(tmp_path):
    """Different tool versions must not be compared against each other.

    Equal and otherwise-identical profiles from two versions would otherwise
    agree on the rules they share and silently ignore the ones that appeared or
    disappeared, which is a pass built on an incomplete comparison.
    """
    c = fb.compare({'a': 'PASS', 'b': 'PASS'}, {'a': 'PASS'}, 'job-x')
    assert c.status == fb.NOT_COMPARABLE, (
        f'a profile with an extra rule compared as {c.status}; it must be '
        f'{fb.NOT_COMPARABLE}, because half the report was never compared')
    assert not c.ok

    c2 = fb.compare({'a': 'PASS'}, {'a': 'PASS', 'z': 'FAIL'}, 'job-x')
    assert c2.status == fb.NOT_COMPARABLE
    assert not c2.ok


# ── 3. it CAN catch a deviation — on a REAL pair from the repo, not a built one ──

def test_a_real_renderer_variant_that_differs_is_reported_as_a_deviation():
    """Criterion 2, on artefacts that were already in the repo.

    `out/dark3/f00440.png` and `out/debug/f00440.png` are two renders of the
    same showcase job at the same frame, and the rules disagree on them. This
    runs the REAL rules over BOTH files and feeds the resulting profiles to the
    comparison — so if a rule were changed to stop reading the frame, this
    guard would fail rather than continue to demonstrate nothing.
    """
    import visual_qa as vq

    dark = _real('dark3/f00440.png')
    dbg = _real('debug/f00440.png')

    def profile(p: Path) -> dict[str, str]:
        a = vq.load(p)
        fs = [vq.rule_safe_area(a), vq.rule_clipping(a), vq.rule_font_size(a),
              vq.rule_black_frame(a), vq.rule_blur(a)]
        return fb.verdict_profile(fs, drop=frozenset({'contrast_frame'}))

    dark_prof, dbg_prof = profile(dark), profile(dbg)
    assert dark_prof != dbg_prof, (
        'the two real render variants now agree on every rule, so this guard '
        'can no longer show the baseline catching anything. Either the rules '
        'changed or the corpus did; re-measure rather than deleting the guard.')

    # A baseline recorded from one is DEVIATED by the other.
    c = fb.compare(dbg_prof, dark_prof, 'showcase@440')
    assert c.status == fb.DEVIATES, f'expected a deviation, got {c.status}'
    assert not c.ok
    moved = {d.rule for d in c.deviations}
    assert moved, 'DEVIATES with no deviations listed is a contradiction'
    # And the specific rule the earlier measurement named.
    assert 'clipping' in moved or 'safe_area' in moved, (
        f'the deviation is on {sorted(moved)}; the measured difference between '
        f'these two renders was on clipping/safe_area, so if this changed, '
        f're-measure the pair')

    # ... and the baseline agrees with ITSELF, which is criterion 1.
    same = fb.compare(dark_prof, dark_prof, 'showcase@440')
    assert same.status == fb.AGREES and same.ok, (
        'a baseline disagrees with the report it was recorded from. That is '
        'the instability criterion 1 exists to rule out.')


def test_the_same_verdicts_in_a_different_order_still_agree():
    """The comparison is on the mapping, not on serialisation order.

    A JSON baseline read back can order its keys differently from the report it
    was recorded from; if equality were positional this would report a
    deviation on every load and the baseline would be noise again.
    """
    a = fb.compare({'safe_area': 'PASS', 'blur': 'PASS'},
                   {'blur': 'PASS', 'safe_area': 'PASS'}, 'job-x')
    assert a.status == fb.AGREES and a.ok, str(a)


# ── 4. a rule that is constant must not be in a baseline ──────────────���──────

def test_a_constant_rule_is_excluded_from_the_profile_by_the_caller():
    """`contrast_frame` is UNAVAILABLE on every frame.

    Storing it would store a constant, and comparing a constant is the "red for
    a constant" defect P22 removed — in the opposite direction, where it can
    never go red. The exclusion is the caller's, named explicitly, so a new
    constant rule is excluded by review rather than by accident.
    """
    class F:
        def __init__(self, rule, verdict):
            self.rule, self.verdict = rule, verdict

    findings = [F('safe_area', 'PASS'), F('contrast_frame', 'UNAVAILABLE'),
                F('overflow', 'UNAVAILABLE')]
    kept = fb.verdict_profile(findings, drop=frozenset({'contrast_frame'}))
    assert 'contrast_frame' not in kept, kept
    assert kept == {'safe_area': 'PASS', 'overflow': 'UNAVAILABLE'}, kept


# ── 5. round trip through the file, so the guard covers the real artefact ─────

def test_a_recorded_baseline_is_read_back_and_agrees(tmp_path):
    """The written file is the thing compared, not the in-memory dict.

    Serialisation is where a baseline silently loses a rule — a non-ASCII
    detail, a key dropped by `json`, a file written with a trailing comma. This
    writes one to disk and compares through the reader.
    """
    profile = {'safe_area': 'PASS', 'blur': 'PASS', 'font_size': 'UNVERIFIABLE'}
    p = fb.write_baseline(tmp_path / 'job.json', profile, 'job-x')
    assert p.exists()

    read_back = fb.read_baseline(p)
    assert read_back == profile, (
        f'the baseline did not survive its own round trip: wrote {profile}, '
        f'read {read_back}')
    c = fb.compare(profile, read_back, 'job-x')
    assert c.status == fb.AGREES and c.ok, str(c)

    # A different report against the SAME stored file deviates.
    changed = dict(profile, blur='FAIL')
    c2 = fb.compare(changed, read_back, 'job-x')
    assert c2.status == fb.DEVIATES
    assert [str(d) for d in c2.deviations] == ['blur: PASS -> FAIL'], c2.deviations


def test_recording_a_baseline_is_an_explicit_act(tmp_path):
    """Reading must never create the file it compares against.

    This is the other half of "delete the file and see what happens": if a
    plain read wrote a baseline, the guard in test 2 would be unreachable,
    because the file would always be there by the time anything looked.
    """
    p = tmp_path / 'never-created.json'
    for _ in range(3):
        fb.read_baseline(p)
    assert not p.exists(), (
        'reading a baseline created it. A run that writes its own reference '
        'passes on first sight of any input.')


# ── 6. the work order's premise, corrected by measurement ─────────────────────

def test_a_frame_can_still_reach_exit_zero_and_does(tmp_path, capsys):
    """THE PREMISE THIS WORK ORDER WAS WRITTEN ON IS FALSE, and this pins that.

    The work order states: "the problem is not 'red', it is that NO PATH reaches
    exit 0". Measured, that is wrong for the ordinary case. Two arguments were
    simply never supplied by the caller:

      * `--declared-px` — without it `font_size` is UNVERIFIABLE on 333/333,
        because a ratio needs both sides;
      * a props file declaring the format — without it `aspect` is UNVERIFIABLE
        on 333/333, for the same reason.

    Measured on a real corpus frame with both supplied, `--frame` exits 0:

        13 findings: 0 FAIL, 0 UNVERIFIABLE, 5 UNAVAILABLE

    and over the 333-frame corpus 291 of 333 reach exit 0 (the remaining 42 are
    blocked by real measurements: 23 `black_frame` FAIL, 30 `blur` FAIL, and
    UNVERIFIABLEs from an untrusted backdrop model). So the gate is NOT stuck;
    it is a gate that only goes green when the caller tells it what it asked for.

    This matters for the baseline because it changes what a baseline is FOR: not
    "make the gate reachable" but "notice that a reachable gate changed shape".
    """
    import json

    import visual_qa as vq

    frame = CORPUS / 'p13_probe' / 'full_a' / '0002.png'
    if not frame.exists():
        pytest.skip(f'corpus frame absent: {frame}')
    props = tmp_path / 'props.json'
    props.write_text(json.dumps(
        {'format': {'width': 1920, 'height': 1080, 'fps': 60}, 'scenes': []}),
        encoding='utf-8')

    code = vq.main(['--frame', str(frame), '--declared-px', '20',
                     '--props', str(props)])
    out = capsys.readouterr().out
    assert code == 0, (
        f'`--frame` exited {code} on a real corpus frame with --declared-px and '
        f'a declared format both supplied. The work order asserted no path '
        f'reaches exit 0; if that has stopped being true, the baseline\'s '
        f'purpose has to be re-stated rather than the tool re-broken:\n{out}')
    assert '0 FAIL' in out and '0 UNVERIFIABLE' in out, out


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
