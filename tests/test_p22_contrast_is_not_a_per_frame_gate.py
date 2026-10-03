"""P22 — the contrast rule is no longer a permanently-red per-frame gate.

WHAT WAS WRONG
--------------
`rule_contrast()` took NO arguments. It read `THEMES` — constants in
`design/themes.ts` — and returned the same 24-pair table whatever frame it was
handed. It was emitted into every `--frame` report, so `visual_qa.py --frame`
exited 1 on all 333 corpus frames for a fact no frame could have caused. A gate
that is red for a constant gates nothing: it cannot distinguish "this frame is
broken" from "the palette has always been this way", so it trains a reader to
ignore red — which is the cost, and the cost is the whole defect.

WHAT IS ASSERTED HERE, AND BY WHAT MEANS
----------------------------------------
Every claim below is reached by RUNNING `vqa.main(argv)` and reading the exit
code and the report. Nothing here asserts that a string appears in a source
file, or that a constant holds a value: this project has been fooled that way
seven times, and `assert 'WCAG_TEXT' in source` would be exactly the wrong guard
for a work order whose subject is "the threshold must not be what changed".

The question this file has to be able to answer is the one the work order asks:

    "IF THE PALETTE WERE FIXED TOMORROW, WOULD THIS GATE GO GREEN?"

and the honest answer for the per-frame path is "no — and it must not, because
that path never measured the palette". So the guards pin BOTH halves: the frame
path must not carry a contrast FAIL, and the theme path must still be able to
FAIL, so the finding is reported rather than deleted.
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'visual_qa.py'
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import visual_qa as vqa  # noqa: E402

import qa_layers as ql  # noqa: E402


# ── fixtures ─────────────────────────────────────────────────────────────────

def _clean_frame(tmp_path: Path) -> Path:
    """A frame every pixel rule can pass, so the exit code is contrast's alone.

    Built to clear `backdrop_model`'s own trust check — content is kept off both
    the EDGE bands and the RING bands — because a frame the instrument distrusts
    yields UNVERIFIABLE, and UNVERIFIABLE also exits 1. That would make this
    fixture unable to tell "the contrast gate fired" from "the frame was
    unmeasurable", which is the confusion this whole file exists to remove.

    The declared format is passed explicitly so `aspect` has both sides, which
    is the other rule that would otherwise answer UNVERIFIABLE on every frame.
    """
    w, h = 320, 120
    bg = np.array(vqa.THEMES['premium-dark']['bg'], dtype=int)
    a = np.zeros((h, w, 3), dtype=int) + bg
    # Two bright bars, interior: clear of EDGE (cols 0..39, 280..319) and of the
    # RING row bands (rows 0..23, 96..119).
    a[50:70, 80:120] = np.array(vqa.THEMES['premium-dark']['ink'])
    a[50:70, 160:200] = np.array(vqa.THEMES['premium-dark']['ink'])
    p = tmp_path / 'clean.png'
    Image.fromarray(a.astype('uint8')).save(p)
    return p


def _run(argv, capsys):
    """Run the real CLI and hand back (exit_code, findings, stdout, stderr)."""
    code = vqa.main([str(a) for a in argv])
    out, err = capsys.readouterr()
    if '--json' in argv:
        findings = json.loads(out)
    else:
        findings = [
            {'rule': r, 'verdict': v, 'value': None, 'detail': d}
            for v, r, _val, d in re.findall(
                r'\[(\w+)\s*\]\s+(\w+)(?:\s+value=(\S+))?\s*\n\s+(.+)', out)]
    return code, findings, out, err


# ── 1. the frame path does not carry the palette's FAIL ─────────────────────

def test_a_clean_frame_no_longer_fails_on_the_palette(tmp_path, capsys):
    """THE headline guard, and the reason this work order existed.

    Before P22 this exited 1 with exactly one FAIL, named `contrast`, on a frame
    that every other rule passes. Now it must exit 0.
    """
    frame = _clean_frame(tmp_path)
    code, findings, out, _ = _run(
        ['--frame', frame, '--declared-px', '20', '--props', _props_file(tmp_path)],
        capsys)
    assert code == 0, (
        f'--frame exited {code} on a frame every pixel rule passes. The only '
        f'remaining non-zero contributors should be rules that measure '
        f'this frame:\n{out}')
    rules = {f['rule'] for f in findings}
    assert 'contrast' not in rules, (
        f'the per-frame report still emits the palette rule: {rules}')
    assert 'theme_contrast' not in rules, (
        f'the palette table leaked onto the frame path: {rules}')


def _props_file(tmp_path: Path) -> Path:
    """A minimal declared format, so `aspect` is not UNVERIFIABLE."""
    p = tmp_path / 'props.json'
    p.write_text(json.dumps({'format': {'width': 320, 'height': 120, 'fps': 24},
                             'scenes': []}), encoding='utf-8')
    return p


def test_the_frame_path_reports_the_contrast_hole_rather_than_hiding_it(tmp_path, capsys):
    """Honest UNAVAILABLE, with the measurement attached.

    Splitting the rule is only acceptable if the per-frame half says out loud
    that it cannot answer. A silent removal would leave the tool claiming
    coverage it does not have — the defect class P21 was about.
    """
    frame = _clean_frame(tmp_path)
    code, findings, out, _ = _run(['--frame', frame, '--json'], capsys)
    hit = [f for f in findings if f['rule'] == 'contrast_frame']
    assert len(hit) == 1, f'expected exactly one rule_contrast_frame finding: {findings}'
    assert hit[0]['verdict'] == vqa.UNAVAILABLE, (
        f'the per-frame contrast rule reports {hit[0]["verdict"]}. UNAVAILABLE is '
        f'the honest answer — the instrument does not exist — and UNVERIFIABLE '
        f'would claim one ran and could not decide:\n{out}')
    assert hit[0]['value'] is None, (
        'UNAVAILABLE findings must carry no number; a number here would be a '
        f'threshold invented rather than measured: {hit[0]}')
    assert code == 1, (
        f'--frame exited {code}; it is expected to be non-zero here because '
        f'font_size and aspect are UNVERIFIABLE without a declared size/format, '
        f'but the contrast finding must not be among the reasons')


# ── 2. the palette table is still reported, and still fails ──────────────────

def test_the_theme_path_still_reports_the_palette_finding_and_still_exits_one(capsys):
    """The finding is SEPARATED, not deleted.

    If `--theme-contrast` could not go red, the split would have thrown away a
    real measurement — 4 pairs below 3:1, 8 below 4.5:1 — and this would be
    "made the gate green" rather than "said where the red belongs".
    """
    code, findings, out, err = _run(['--theme-contrast', '--json'], capsys)
    hit = [f for f in findings if f['rule'] == 'theme_contrast']
    assert len(hit) == 1, f'expected one theme_contrast finding: {findings}'
    assert hit[0]['verdict'] == vqa.FAIL, (
        f'the palette table no longer FAILs, so either the palette was fixed '
        f'(it was not — themes.ts is untouched) or the rule stopped reporting: '
        f'{hit[0]}')
    assert code == 1, f'--theme-contrast must exit 1 on a failing palette, got {code}\n{out}'
    assert 'FAIL' in err, 'the summary line must state the FAIL'


def test_the_theme_finding_still_names_the_eight_pairs_and_the_worst(capsys):
    """The measurement survives the refactor, exactly."""
    _, findings, _, _ = _run(['--theme-contrast', '--json'], capsys)
    hit = next(f for f in findings if f['rule'] == 'theme_contrast')
    assert len(hit['extra']['failing_text_bar']) == 8, (
        f'the palette still fails 8 pairs below 4.5:1 and this reports '
        f'{hit["extra"]["failing_text_bar"]}')
    worst = min(hit['extra']['pairs'], key=lambda p: p['ratio'])
    assert worst['pair'] == 'premium-light/inkFaint on bg', worst
    assert worst['ratio'] == 2.16, worst


def test_the_theme_flag_does_not_change_the_frame_exit_code(tmp_path, capsys):
    """Adding the flag to a frame run must not smuggle the FAIL back in."""
    frame = _clean_frame(tmp_path)
    props = _props_file(tmp_path)
    code_without, _, _, _ = _run(
        ['--frame', frame, '--declared-px', '20', '--props', props], capsys)
    code_with, findings, out, _ = _run(
        ['--frame', frame, '--declared-px', '20', '--props', props,
         '--theme-contrast'], capsys)
    assert code_with == code_without == 0, (
        f'frame run exits {code_without} without the flag and {code_with} with '
        f'it. A palette FAIL must not reach a frame exit code:\n{out}')
    rules = {f['rule'] for f in findings}
    assert 'theme_contrast' in rules, (
        f'the flag was passed and the table was not reported: {rules}')


# ── 3. the thresholds did NOT move (this is the guard against "make it green") ──

def test_neither_wcag_threshold_moved():
    """The work order's forbidden move, pinned as a VALUE rather than a grep.

    `assert 'WCAG_TEXT' in source` would pass if someone redefined the constant
    to 2.0 and left the name. Asserting the number is what makes this the guard
    against "lower the threshold until the gate is green" — which the work order
    names as the most dangerous option, and which this implementation rejects by
    construction: no threshold was changed, because no threshold was the defect.
    """
    assert vqa.WCAG_TEXT == 4.5, (
        'WCAG_TEXT moved. Lowering it until the palette passes is the change '
        'this work order forbids; raising it needs a stated WCAG basis.')
    assert vqa.WCAG_LARGE == 3.0, 'WCAG_LARGE moved'


def test_the_palette_itself_is_untouched():
    """`design/themes.ts` is not modified by this work order.

    Changing a palette value is a DESIGN decision, out of scope: this work order
    says "advise, do not implement". Asserting the values pins that boundary, so
    a later commit that recolours the palette to make a guard pass is visible.
    """
    assert vqa.THEMES['premium-light']['inkFaint'] == (0x14, 0x14, 0x0F, 0.34)
    assert vqa.THEMES['premium-dark']['inkFaint'] == (0xF5, 0xF2, 0xEA, 0.34)
    assert vqa.THEMES['premium-light']['accent'] == (0xA8, 0x80, 0x1F)
    assert vqa.THEMES['premium-light']['positive'] == (0x1E, 0x8E, 0x4A)


# ── 4. the separation is structural, not a name in a deny-list ────────────────

def test_the_palette_rule_still_takes_no_arguments():
    """The claim the whole diagnosis rests on, re-measured.

    If `rule_contrast` ever grew a frame argument, the split would be wrong and
    this fails rather than letting a stale comment survive.
    """
    assert not inspect.signature(vqa.rule_contrast).parameters, (
        'rule_contrast now takes arguments, so the palette lookup IS reading '
        'something — re-measure whether it belongs on the frame path')


def test_frame_scoped_rules_is_exactly_the_rules_that_take_a_frame():
    """The scope table is a FACT about the code, re-derived by calling it.

    This is what stops the split decaying into an exemption list: a rule that
    stops reading frames fails here instead of inheriting an exemption nobody
    chose, and a new frame rule fails here until it is declared.
    """
    takes_a_frame = set()
    for name in ql._rule_functions():
        if name == 'rule_contrast':
            continue          # the palette rule, deliberately not frame-scoped
        params = list(inspect.signature(getattr(vqa, name)).parameters)
        # First parameter is `a` (the frame) for frame rules; a pair rule's
        # first two are both paths, and a props rule's is a dict or a Path.
        if params:
            ann = str(inspect.signature(getattr(vqa, name)).parameters[params[0]].annotation)
            if 'ndarray' in ann:
                takes_a_frame.add(name.replace('rule_', ''))
    assert takes_a_frame, (
        'no rule was detected as taking a frame — the probe is broken, not the '
        'tool. A guard that measures nothing must not be allowed to pass.')
    assert takes_a_frame <= vqa.FRAME_SCOPED_RULES, (
        f'rules that take a frame but are not declared frame-scoped: '
        f'{takes_a_frame - vqa.FRAME_SCOPED_RULES}')
    assert 'theme_contrast' not in vqa.FRAME_SCOPED_RULES, (
        'theme_contrast takes no frame and must not be exempt from the frame '
        'path by accident')


def test_the_layer_partition_knows_about_the_split():
    """qa_layers must classify both halves, or its report is stale prose."""
    report = ql.build_report()
    assert set(report['layer_of']) >= {'contrast_frame', 'theme_contrast'}
    assert report['behaviour']['theme_contrast']['requires_pair'] is False
    assert report['behaviour']['theme_contrast']['behaves_like_static'] is True
    assert report['layer_of']['contrast_frame'] == 'Visual'


def test_the_partition_probe_can_actually_still_call_every_rule():
    """The probe calls all rules; a rule it cannot call would silently vanish.

    `_emitted_names` swallows exceptions into a string, so a rule that raises
    would leave an `<ERROR ...>` entry and the partition would be asserted over
    a table built from a failure. This says so.
    """
    emitted = ql._emitted_names()
    broken = {k: v for k, v in emitted.items() if any(x.startswith('<ERROR')
                                                   for x in v)}
    assert not broken, f'qa_layers could not call these rules: {broken}'
    assert 'theme_contrast' in emitted['rule_contrast'], emitted['rule_contrast']
    assert 'contrast_frame' in emitted['rule_contrast_frame'], emitted['rule_contrast_frame']


# ── 5. the diagnosis is pinned as behaviour, not as a comment ────────────────

def test_contrast_frame_is_the_same_verdict_on_frames_that_differ():
    """It is UNAVAILABLE because the instrument is absent, not because it
    measured and could not decide — so two very different frames agree."""
    a = np.zeros((120, 320, 3), dtype=int) + 12
    b = a.copy()
    b[50:70, 80:120] = 240
    assert (vqa.rule_contrast_frame(a).verdict
            == vqa.rule_contrast_frame(b).verdict == vqa.UNAVAILABLE)
    assert vqa.rule_contrast_frame(a).value is None
    assert vqa.rule_contrast_frame(a).trusted is False, (
        'UNAVAILABLE findings are marked untrusted throughout this tool; a '
        'trusted one would claim the instrument ran')


def test_every_measured_inkfaint_consumer_is_text_and_the_table_says_so():
    """The consumption measurement, pinned as data the rule can be held to.

    If someone later reassigns `inkFaint` to a divider role, this is where the
    change shows up — and `CONTRAST_ROLES` is what would have to be re-measured.
    """
    assert set(vqa.CONTRAST_ROLES) >= {'inkFaint', 'accent', 'positive'}
    faint = vqa.CONTRAST_ROLES['inkFaint']
    assert faint['consumers'] == 'text', (
        'inkFaint was measured at 10 of 10 sites being text labels and data '
        'numbers. If that has changed, re-measure the sites, do not edit this '
        f'line: {faint}')
    assert faint['sites'] == 10, faint
    positive = vqa.CONTRAST_ROLES['positive']
    assert positive['consumers'] == 'text'
    assert positive['sites'] == 2, positive


def test_the_theme_row_table_is_the_one_the_rule_reports():
    """One definition. A guard must not be able to pass on a table the rule
    does not use, which is how the split could have produced two truths."""
    rows = vqa.theme_contrast_rows()
    finding = vqa.rule_contrast()[0]
    assert finding.extra['pairs'] == rows
    assert len(rows) == 24
    assert {r['role'] for r in rows} == {'ink', 'inkMuted', 'inkFaint', 'accent',
                                        'positive', 'negative'}
    assert {r['theme'] for r in rows} == {'premium-dark', 'premium-light'}


def test_json_mode_keeps_the_separation(tmp_path, capsys):
    """A machine consumer must not see a per-frame FAIL it cannot act on."""
    frame = _clean_frame(tmp_path)
    code, findings, out, _ = _run(['--frame', frame, '--json'], capsys)
    assert json.loads(out) == findings
    verdicts = {f['rule']: f['verdict'] for f in findings}
    assert verdicts.get('contrast_frame') == vqa.UNAVAILABLE
    assert 'contrast' not in verdicts and 'theme_contrast' not in verdicts


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))