"""P21 — the `--props` path must be able to say the graph is wrong (verdict C).

THE DEFECT THIS GUARDS. Measured, not quoted: poisoning every one of the 49
strings in the delivered showcase graph — all four scenes' content included —
produced a QA report BYTE-IDENTICAL to the clean graph's, with the same exit
code, and so did the clean graph (0). Five findings, four of them UNAVAILABLE
placeholders, and the one real rule (`missing_asset`) never reads its `props`
argument. That path did not gate errors, and it did not gate correct graphs
either. It was decoration reporting green.

VERDICT C, and the two halves are not the same answer:

  * `radius` / `shadow` / `depthCue` must NOT get a file-existence check.
    Measured: `radius` cannot carry a path at all (`mergeSection` keeps a value
    only when its typeof matches the default's, and `RADIUS` is all numbers, so
    a poisoned string is dropped before any file could be named); `shadow` and
    `depthCue` DO pass strings through, and they are CSS declarations handed to
    `boxShadow`. A missing `url()` target is a paint failure the browser
    resolves — not a missing deliverable this gate owns. That ruling is pinned
    below so it cannot be quietly re-litigated into a rule.
  * The scene graph's relationship to the renderer IS checkable, with no
    threshold at all. `MissingScene` is the fallback for any type
    `SCENE_RENDERERS` does not name, and it renders the words "not implemented
    in P4". Measured: 22 types declared, 13 rendered, 9 in between.

WHY EVERY ASSERTION HERE CALLS `main(argv)`. This project has been fooled by
text-presence assertions seven times, and the falsest of them is the shape this
file could have taken: asserting that `graph_scene_renderable` appears in
visual_qa.py's source proves a string is in a file, not that the tool can fail.
So nothing here reads the source to decide whether the gate works. Each test
runs the entry point and reads the RETURN VALUE and the REPORT. The only source
reading in this file is in the test that pins the B ruling, and it exists to
assert an ABSENCE — that a rule which would be wrong is not there.

WHY BOTH DIRECTIONS ARE IN ONE FILE. A guard that only checks the failing case
is satisfied by `return 1` unconditionally, by an always-FAIL implementation, by
anything at all that is "safe" and useless. Mutation 2 in the verification
protocol injects exactly that; the healthy-direction test is what kills it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'visual_qa.py'
sys.path.insert(0, str(SCRIPT.parent))
import visual_qa as vqa  # noqa: E402

RULE = 'graph_scene_renderable'


# ── fixtures: graphs written here, never borrowed from out/ ──────────────────
#
# `studio/public/jobs/**` is a gitignored staging copy (stage_showcase.py writes
# it) and `out/` is gitignored entirely, so a fixture taken from either passes on
# the machine that made it and skips or fails everywhere else. Everything below
# is written by the test.

def _props(tmp_path: Path, name: str, doc: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return p


def _clean_graph() -> dict:
    """A graph every declared scene type can actually draw.

    Deliberately uses two DIFFERENT rendered types (`kpi-hero` and
    `bar-chart`) rather than repeating one, so the rule cannot pass by counting
    scenes instead of resolving types.
    """
    return {
        'version': 1,
        'project': 'p21_guard',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'bpm': 126,
        'scenes': [
            {'id': 'g_one', 'type': 'kpi-hero', 'durationInFrames': 120,
             'content': {'value': 1}},
            {'id': 'g_two', 'type': 'bar-chart', 'durationInFrames': 120,
             'content': {'chart': {'type': 'bar', 'labels': ['a', 'b']}}},
        ],
    }


def _poison_all_strings(node, tag: str = 'POISONED') -> tuple:
    """Replace EVERY string in the document, recursively. Returns (node, count).

    The whole point of the original defect: a path that cannot notice this has
    no idea what the graph says. Note this KEEPS the scene `type` values as
    legal rendered types by rebuilding from the clean graph and poisoning only
    the data; see `test_the_poison_is_not_vacuous`, which asserts the poison
    actually changed the file, because a poisoned fixture identical to the clean
    one would make every comparison below trivially true.
    """
    count = [0]

    def walk(x):
        if isinstance(x, str):
            count[0] += 1
            return '%s_%d' % (tag, count[0])
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(node), count[0]


def _main(argv, capsys):
    """Call the real entry point and return (exit code, report text)."""
    code = vqa.main([str(a) for a in argv])
    return code, capsys.readouterr().out


def _verdict_for(report: str, rule: str) -> str | None:
    """The verdict the CLI PRINTED for `rule`, or None if it never ran.

    Read back out of the printed report rather than out of a Finding list, on
    purpose: the question this file asks is what a reader of the report sees,
    not what the library returned.
    """
    for line in report.splitlines():
        if not line.startswith('  ['):
            continue
        parts = line.split(']')
        if len(parts) < 2:
            continue
        body = parts[1].split()
        if body and body[0] == rule:
            return parts[0].lstrip(' [').strip()
    return None


# ── the discriminating question ─────────────────────────────────────────────

def test_the_failure_direction_a_graph_with_no_renderer_is_reported_and_exits_nonzero(
        tmp_path, capsys):
    """The one question this whole work order asks: does `--props` notice?

    ⚠️ REWRITTEN 2026-10-09 (P26). This fixture used `quote` as the example of a
    declared type with no renderer. P26 gave `quote` a real renderer (and
    `outro`, `card-grid`, and four others), so that example became false and this
    test went red — correctly. Per the P14 precedent the fixture is rewritten to
    a type that STILL has no renderer, and the ruling that leaves one there is
    pinned in `test_p26_scene_type_coverage.py`. `video` is a member of
    `GENERATIVE_SCENE_TYPES` and is deliberately left to `MissingScene` (no
    generative renderer exists; P17). The ASSERTIONS are unchanged: a graph whose
    only scene type has no renderer must be reported FAIL and must exit non-zero.
    """
    doc = _clean_graph()
    doc['scenes'] = [{'id': 'g_one', 'type': 'video', 'durationInFrames': 120,
                      'content': {'text': 'hello'}}]
    p = _props(tmp_path, 'gap.json', doc)

    code, report = _main(['--props', p], capsys)

    assert _verdict_for(report, RULE) == vqa.FAIL, (
        f'a graph whose only scene type has no renderer was not reported as '
        f'FAIL. Before P21 this path could not see it at all.\n{report}'
    )
    assert code != 0, (
        f'main() returned {code} for a graph that renders "not implemented in '
        f'P4" for its whole duration. CI gates on this number.\n{report}'
    )
    assert 'not implemented in P4' in report, (
        'the report must name what the viewer would actually see, or the caller '
        f'cannot act on it:\n{report}'
    )


def test_the_failure_direction_names_the_offending_scene_and_type(tmp_path, capsys):
    """A count is not enough: with 10 scenes, "1 FAIL" does not say which.

    ⚠️ REWRITTEN 2026-10-09 (P26), same reason and same shape as the test above:
    the fixture's `outro` now has a renderer, so it was swapped for
    `data-plane-3d`, which is still left to `MissingScene`.
    """
    doc = _clean_graph()
    doc['scenes'].append({'id': 'g_gap', 'type': 'data-plane-3d', 'durationInFrames': 60})
    p = _props(tmp_path, 'one_gap.json', doc)

    code, report = _main(['--props', p], capsys)

    assert _verdict_for(report, RULE) == vqa.FAIL, report
    assert 'data-plane-3d' in report, f'the offending type is not named:\n{report}'
    assert code != 0


def test_the_healthy_direction_a_fully_renderable_graph_still_exits_zero(
        tmp_path, capsys):
    """The half that catches an always-FAIL implementation. Mutation 2.

    The failure test above is satisfied by `return 1` unconditionally, by an
    unconditional FAIL, and by anything else that is 'safe' and useless. This
    is the assertion that distinguishes 'reports a gap' from 'refuses to run'.
    """
    p = _props(tmp_path, 'clean.json', _clean_graph())
    code, report = _main(['--props', p], capsys)

    assert _verdict_for(report, RULE) == vqa.PASS, (
        f'a graph whose every scene type has a renderer must PASS; got '
        f'{_verdict_for(report, RULE)!r}\n{report}'
    )
    assert code == 0, (
        f'main() returned {code} on a healthy graph. The gate must reject bad '
        f'graphs WITHOUT rejecting good ones.\n{report}'
    )


def test_the_healthy_direction_is_not_vacuous(tmp_path, capsys):
    """`code == 0` plus no output is what a tool that returned early gives."""
    p = _props(tmp_path, 'clean.json', _clean_graph())
    code, report = _main(['--props', p], capsys)
    assert code == 0
    assert _verdict_for(report, RULE) is not None, (
        f'the healthy props-only run printed no {RULE} finding at all, so it is '
        f'not evidence the rule ran:\n{report}'
    )


def test_the_delivered_demo_graph_is_clean_and_the_gate_stays_green(
        tmp_path, capsys):
    """The real delivered graph, re-run from its tracked source.

    Read from `pipeline/examples/showcase_demo.json`, NOT from
    `studio/public/jobs/**`: that is a gitignored staging copy whose contents
    depend on whichever graph was staged last, so a guard pointing at it would
    be a guard against local scratch state. Skipped rather than failed if the
    tracked example is absent, and says which it did.
    """
    demo = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'
    if not demo.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent')
    code, report = _main(['--props', demo], capsys)

    assert _verdict_for(report, RULE) == vqa.PASS, (
        f'the delivered showcase demo was reported {code} — it uses '
        f'kpi-hero / browser-stack / dashboard / calendar, all of which have '
        f'renderers. A FAIL here means the rule is wrong, not the graph.\n{report}'
    )
    assert code == 0, f'the delivered demo must stay green; exit was {code}\n{report}'


# ── the question the command window actually asked ──────────────────────────

def test_poisoning_the_graph_changes_the_report_and_the_exit_code(tmp_path, capsys):
    """The original measurement, re-run as a guard.

    Every string in the graph replaced, all four scenes included. Before P21 the
    report was byte-identical and the exit code was the same for both. Now the
    poison must be visible — because the poisoned `id`s no longer match
    `/^[a-z0-9_]+$/`... no: because the poisoned scene TYPES are undeclared,
    which the rule reports alongside the verdict. Either way the assertion is
    on the OBSERVED report and exit code, not on which of the two reasons fired.
    """
    clean = _props(tmp_path, 'clean.json', _clean_graph())
    poisoned_doc, n = _poison_all_strings(_clean_graph())
    poisoned = _props(tmp_path, 'poisoned.json', poisoned_doc)

    assert n > 0, 'the poison replaced nothing, so every comparison here is vacuous'
    assert poisoned.read_bytes() != clean.read_bytes(), (
        'the poisoned graph is byte-identical to the clean one; the fixture is '
        'not doing what its name says'
    )

    code_clean, report_clean = _main(['--props', clean], capsys)
    code_poison, report_poison = _main(['--props', poisoned], capsys)

    assert report_clean != report_poison, (
        'the --props report is identical for a clean graph and for one whose '
        'every string has been replaced. This is the exact defect P21 was '
        'written against, and it is back.\n'
        f'--- clean ---\n{report_clean}\n--- poisoned ---\n{report_poison}'
    )
    assert code_clean != code_poison, (
        f'exit code is {code_clean} for both a clean graph and a poisoned one'
    )


def test_the_rule_reads_the_graph_rather_than_wearing_a_props_argument(tmp_path,
                                                                     capsys):
    """The P18 observation about `missing_asset`, restated for the new rule.

    Two DIFFERENT graphs, same run shape, different reports. A function that
    ignores its argument produces identical output, which is what made
    `missing_asset` a repository check in a props argument's clothing.
    """
    good = _props(tmp_path, 'good.json', _clean_graph())
    bad_doc = _clean_graph()
    # ⚠️ REWRITTEN 2026-10-09 (P26): was `card-grid`, which P26 gave a renderer.
    # Swapped for `video`, which is still deliberately unrendered. The claim is
    # unchanged: a rule that reads the graph produces different output for two
    # different graphs.
    bad_doc['scenes'][1]['type'] = 'video'
    bad = _props(tmp_path, 'bad.json', bad_doc)

    code_good, report_good = _main(['--props', good], capsys)
    code_bad, report_bad = _main(['--props', bad], capsys)

    assert report_good != report_bad
    assert _verdict_for(report_good, RULE) == vqa.PASS
    assert _verdict_for(report_bad, RULE) == vqa.FAIL
    assert code_good == 0 and code_bad != 0


# ── the B ruling, pinned so it cannot be quietly reversed ────────────────────

def test_the_props_path_has_no_rule_that_checks_a_style_section_for_files(tmp_path):
    """Verdict C's first half, as an ABSENCE.

    The work order asked whether `radius` / `shadow` / `depthCue` should get a
    "the graph declares a path and the disk does not have it" check. The
    measured answer is no, and this test exists so that answer is a recorded
    decision rather than a gap someone fills later on the reasonable-sounding
    misreading that "the style bible is now schema-declared, so paths must be
    checkable there too".

    It reads the source for the one thing source-reading can decide — whether a
    function named like an asset check mentions a style section — and asserts
    the function does not. Every OTHER assertion in this file calls `main()`.
    """
    src = Path(vqa.__file__).read_text(encoding='utf-8')
    m = re.search(r'def rule_missing_asset\(props: dict\).*?(?=\ndef |\nclass )', src, re.S)
    assert m, 'rule_missing_asset not found'
    body = m.group(0)
    code = re.sub(r'""".*?"""', '', body, flags=re.DOTALL)
    code = re.sub(r'#.*', '', code)
    for section in ('radius', 'shadow', 'depthCue', 'style_bible', 'typography'):
        assert section not in code, (
            f'rule_missing_asset now inspects style_bible.{section}. That check '
            'was measured and rejected in P21: radius/spacing cannot carry a '
            'path (mergeSection drops a value whose typeof differs from the '
            "default's), and shadow/depthCue are CSS strings handed to "
            'boxShadow, where a missing url() target is a paint failure the '
            'browser resolves rather than a missing deliverable.'
        )


def test_the_radius_section_cannot_carry_a_path_in_the_first_place():
    """The measurement behind the ruling above, re-derived rather than asserted.

    `mergeSection` only keeps an incoming value when `typeof v === typeof
    base[key]`. `RADIUS` is `{chip: 999, card: 20, window: 14, panel: 28}` —
    all numbers — so a poisoned string in `radius` cannot survive the merge and
    no rule could ever read a path out of it. This test states the premise in
    data rather than in prose, so a future change to RADIUS that made it
    string-typed would go red here and reopen the question deliberately.
    """
    tokens = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
              / 'design' / 'tokens.ts').read_text(encoding='utf-8')
    m = re.search(r'export const RADIUS = \{(.*?)\}', tokens, re.S)
    assert m, 'RADIUS not found in tokens.ts'
    values = re.findall(r'\w+:\s*([^,\n]+)', m.group(1))
    assert values, 'RADIUS parsed to nothing'
    non_numeric = [v for v in values if not re.match(r'^\s*-?\d', v)]
    assert not non_numeric, (
        f'RADIUS now holds non-numeric values {non_numeric}. mergeSection keeps '
        'a graph value only when its typeof matches the default, so a '
        'string-typed RADIUS could carry a path — and the P21 verdict on '
        'style sections would have to be re-measured rather than inherited.'
    )


def test_the_sections_the_order_named_are_really_declared(tmp_path):
    """`radius` / `shadow` / `depthCue` DO reach the schema — measured, not assumed.

    The ruling above is that they should not be asset-checked. This asserts the
    PREMISE that they are live sections at all, because the natural way to
    argue against it later is to say they were declared but stripped, and that
    argument is currently false (they were declared by `836f532` and consumed
    by real scenes). If they are ever stripped again, the test says which of
    the two worlds we are in.
    """
    schema = (ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts').read_text(
        encoding='utf-8')
    m = re.search(r'export const StyleBibleSchema\s*=\s*z\s*\n?\s*\.object\(\{\s*\n(.*?)\n\s*\}\)',
                  schema, re.S)
    assert m, 'StyleBibleSchema not found'
    keys = set(re.findall(r'^[ \t]+(\w+):', m.group(1), re.M))
    for section in ('radius', 'shadow', 'depthCue'):
        assert section in keys, (
            f'StyleBibleSchema no longer declares {section}. If it was stripped, '
            'a graph can no longer set it and the P21 question about these '
            'sections is closed for a different reason than the one recorded.'
        )


# ── the props path still answers for a graph it cannot read ──────────────────

def test_a_graph_with_no_scenes_is_unverifiable_not_pass(tmp_path, capsys):
    """A report-data props file is not a scene graph, and saying PASS is a lie.

    `qa_report.py` gates the report-pipeline props, which carry `format` and
    `totalDuration` and no `scenes`. Those must not be reported as clean scene
    graphs. UNVERIFIABLE is the project's word for "the instrument could not
    measure it" (this file's header, point 2) and it exits non-zero, so a
    caller gating on the code can tell it from a graph that was checked.
    """
    p = _props(tmp_path, 'report.json',
               {'format': {'width': 1080, 'height': 1920, 'fps': 30},
                'totalDuration': 29.9})
    code, report = _main(['--props', p], capsys)

    assert _verdict_for(report, RULE) == vqa.UNVERIFIABLE, (
        f'a props file with no scenes must not report PASS for the scene check; '
        f'PASS would claim a graph was verified when there was no graph.\n{report}'
    )
    assert code != 0, f'exit was {code}; an unverifiable check must not exit 0'


def test_the_rule_survives_the_json_output_mode(tmp_path, capsys):
    """A consumer reading --json must see the finding, not just the summary.

    The same reason the missing-props UNVERIFIABLE is asserted in JSON mode in
    test_visual_qa.py: a verdict that only appears in the human branch leaves a
    machine reader with a clean array and a non-zero code, which is better than
    silence and still not a report that explains itself.
    """
    doc = _clean_graph()
    doc['scenes'] = [{'id': 'g_one', 'type': 'video', 'durationInFrames': 60}]
    p = _props(tmp_path, 'video.json', doc)

    code = vqa.main(['--props', str(p), '--json'])
    out = capsys.readouterr().out
    findings = json.loads(out)

    assert code != 0
    hit = [f for f in findings if f['rule'] == RULE]
    assert hit, f'the JSON report carries no {RULE} finding: {findings}'
    assert hit[0]['verdict'] == vqa.FAIL, hit[0]
    assert hit[0]['value'] == 1, hit[0]
    # The evidence travels with the verdict, or a consumer cannot act on it.
    assert hit[0]['extra']['gaps'] == [{'index': 0, 'type': 'video'}], hit[0]['extra']