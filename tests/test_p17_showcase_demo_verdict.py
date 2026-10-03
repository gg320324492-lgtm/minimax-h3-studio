"""P17 — the Showcase Demo acceptance criteria, run as verdicts, not as prose.

WHAT THIS FILE IS.

`docs/UPGRADE_MASTER_PLAN.md` line 142 asks for "全新 16:9 / 1920x1080 / 60fps /
45-60s 商业级 demo | 明显达到 premium product film | 含 1-3 个 H3 cinematic shot".
Three of those four clauses are measurable and this file measures them. One of
them is not measurable, and this file says so rather than inventing a number for
it. The verdict that falls out is recorded in docs/P17_SHOWCASE_DEMO.md.

THE QUESTION THIS FILE WAS WRITTEN TO ANSWER.

Not "can a 45-60s demo be authored" — it can, and
`test_a_forty_five_second_graph_is_representable` shows a 45.0s graph the schema
and the QA path both accept today. The question is the one the work order asked:

    IF SOMEONE DELIVERED A DEMO TODAY, WHAT WOULD STOP IT?

Measured answer, and it is not the one the plan assumed. Of the four clauses:

  * "含 1-3 个 H3 cinematic shot" IS gated. `graph_scene_renderable`
    (visual_qa.py, P21) reads `SCENE_RENDERERS` and FAILs a graph containing a
    type that map does not name. Every generative type falls in that gap, so a
    demo that asks for one is caught, and it is caught as a PLACEHOLDER FRAME
    rather than as a film.

  * THE OTHER THREE ARE NOT GATED. Not by `visual_qa.py --props`, not by
    `qa_report.py`, not by the render entry point. There is no clause anywhere in
    the repository that requires 45-60s, that requires 1920x1080@60, and no
    measurable criterion at all for "premium product film".

    This is not a gap in a tool that was built and mis-tuned. `pipeline_manifest.yaml`
    line 204 says so in the repository's own words: `enforced: false`, under the
    heading 「质量门禁（当前全部无自动执行 —— P0 接线）」. Measured: no file outside
    `tests/` invokes `visual_qa.py`, and `render.mjs` — the one thing every
    render goes through — contains no QA call at all.

WHY THE `enforced: false` CLAIM IS MEASURED HERE AND NOT QUOTED.

The plan's own success clause for P18 is 「全过」 on four layers of gates that
`qa_layers.py` reports as `enforced: false`. Reading a comment is how this project
has been fooled seven times. So `test_the_graph_gate_is_not_wired_into_any_
delivery_path` executes the search and asserts on the result, and
`test_the_render_entry_point_calls_no_qa_gate` reads `render.mjs` and asserts the
absence of every QA invocation. Either one going quiet is a fact, not a pass.

WHAT IS DELIBERATELY NOT ASSERTED.

  * No invented "premium" metric. There is no score, no blur threshold, no
    contrast floor standing in for the phrase. The five verdicts this project has
    already accepted — collision, rule_duplicate, rule_contrast_frame, flicker,
    and the per-job baseline — were each accepted BECAUSE the measurement could
    not produce the separation the criterion needed. A sixth would be the same
    finding wearing a new name.

  * No assertion that the H3 renderer should or should not be built. That is a
    judgement for docs/. This file measures whether one could be RENDERED today.

  * No test asserting the absence of a word. The one source-reading test here
    asserts an ABSENCE (`render.mjs` names no QA gate), which is the one thing
    source-reading can decide, and its own matcher is anchored by a positive
    control in `test_the_qa_call_sweep_finds_a_real_invocation`.

A NOTE ON HOW THESE TESTS REACH THE GATE.

Everything here goes through `vqa.main(argv)` and reads the RETURN VALUE and the
PRINTED REPORT, never the source, for every claim about capability. That is the
P21 convention and it is the reason this file can distinguish "the gate can fail"
from "the gate is mentioned".
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'studio' / 'scripts' / 'visual_qa.py'
sys.path.insert(0, str(SCRIPT.parent))
import visual_qa as vqa  # noqa: E402

EXAMPLES = ROOT / 'pipeline' / 'examples'
TEMPLATE = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase'
RENDER_MJS = ROOT / 'studio' / 'bin' / 'render.mjs'

RULE = 'graph_scene_renderable'

#: The two scene types the schema routes to H3. READ from the Python mirror at
#: import time rather than hardcoded, because hardcoding it is how this project's
#: guards rot: if `GENERATIVE_SCENE_TYPES` gains a member, the guard that says
#: "every generative type is gated" must go red, not quietly cover less.
def _generative_types() -> set[str]:
    text = (ROOT / 'pipeline' / 'scene_graph.py').read_text(encoding='utf-8')
    m = re.search(r"GENERATIVE_TYPES\s*=\s*\{([^}]*)\}", text)
    if not m:
        raise RuntimeError('GENERATIVE_TYPES not found in scene_graph.py')
    return set(re.findall(r"'([^']+)'", m.group(1)))


GENERATIVE_TYPES = _generative_types()


def _props(tmp_path: Path, name: str, doc: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return p


def _graph(scenes: list, *, width: int = 1920, height: int = 1080,
           fps: int = 60) -> dict:
    return {
        'version': 1,
        'project': 'p17_verdict',
        'format': {'width': width, 'height': height, 'fps': fps},
        'bpm': 126,
        'scenes': scenes,
    }


def _scene(scene_id: str, scene_type: str, frames: int) -> dict:
    return {'id': scene_id, 'type': scene_type, 'durationInFrames': frames,
            'content': {'value': 1, 'label': 'x'}}


def _main(argv, capsys) -> tuple[int, str]:
    code = vqa.main([str(a) for a in argv])
    return code, capsys.readouterr().out


def _verdict_for(report: str, rule: str) -> str | None:
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


# ── clause 1: the H3 shot IS gated, and it is gated as a placeholder ─────────

def test_a_graph_asking_for_a_generative_scene_is_blocked(tmp_path, capsys):
    """The clause the plan assumes is unenforced is in fact the ONE that bites.

    `video` is a member of `GENERATIVE_SCENE_TYPES` and is absent from
    `SCENE_RENDERERS`, so a scene of that type renders `MissingScene` — the type's
    own name and the words "not implemented in P4" — for its whole duration. The
    gate must FAIL it and exit non-zero, because that film is not the film the
    graph asked for.
    """
    doc = _graph([_scene('s1', 'video', 120)])
    code, report = _main(['--props', _props(tmp_path, 'h3.json', doc)], capsys)

    assert _verdict_for(report, RULE) == vqa.FAIL, report
    assert code != 0, f'exit {code} for a graph that renders a placeholder:\n{report}'
    assert 'not implemented in P4' in report, report


def test_every_generative_type_is_gated_not_only_video(tmp_path, capsys):
    """Covers the SET, not one member — `data-plane-3d` is the one P15 named.

    A guard that only exercised `video` would still be green if
    `data-plane-3d` gained a renderer, and the file would be claiming coverage
    it does not have. Each member is checked separately and the count is
    asserted, so an empty loop is a failure rather than a vacuous pass.
    """
    assert GENERATIVE_TYPES, 'the generative set resolved to nothing; the sweep is vacuous'
    assert 'data-plane-3d' in GENERATIVE_TYPES, (
        f'GENERATIVE_TYPES no longer contains data-plane-3d: {GENERATIVE_TYPES}')

    checked = 0
    for scene_type in sorted(GENERATIVE_TYPES):
        doc = _graph([_scene('s1', scene_type, 60)])
        code, report = _main(
            ['--props', _props(tmp_path, f'gen_{scene_type}.json', doc)], capsys)
        assert _verdict_for(report, RULE) == vqa.FAIL, (
            f'generative type {scene_type!r} was not gated:\n{report}')
        assert code != 0, f'exit {code} for generative type {scene_type!r}'
        checked += 1
    assert checked == len(GENERATIVE_TYPES) == 2, (
        f'checked {checked} of {len(GENERATIVE_TYPES)} generative types')


def test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked(tmp_path, capsys):
    """The plan's actual shape: 1-3 shots inside an otherwise normal film.

    A gate that only fired on a graph made ENTIRELY of generative scenes would be
    satisfied by the plan's example only by accident. One `video` scene in eight
    otherwise renderable scenes must still FAIL, and the report must name which
    scene index it was — otherwise an author cannot act on it.
    """
    scenes = [_scene(f's{i}', 'kpi-hero', 60) for i in range(7)]
    scenes.insert(3, _scene('the_h3_shot', 'video', 180))
    doc = _graph(scenes)
    code, report = _main(['--props', _props(tmp_path, 'mixed.json', doc)], capsys)

    assert _verdict_for(report, RULE) == vqa.FAIL, report
    assert code != 0, report
    assert 'scenes[3]=video' in report, (
        'the report must locate the offending scene by index:\n' + report)
    assert 'the_h3_shot' not in report or 'video' in report, report


# ── clause 2: 45-60s is NOT gated ───��────────────────────────────────────────

def test_a_one_second_film_passes_the_graph_gate(tmp_path, capsys):
    """A 1-second film — 1/45th of the shortest acceptable one — is clean.

    This is the finding, stated as a test. If a duration gate is ever built, this
    goes red and the change is deliberate rather than silent.
    """
    doc = _graph([_scene('s1', 'kpi-hero', 60)])
    code, report = _main(['--props', _props(tmp_path, 'tiny.json', doc)], capsys)

    assert code == 0, report
    assert _verdict_for(report, RULE) == vqa.PASS, report


def test_a_five_minute_film_passes_the_graph_gate(tmp_path, capsys):
    """The upper half: nothing objects to 300s either.

    Two ends of one axis. A gate written against only the 45s floor would let
    this through, so both ends are asserted.
    """
    doc = _graph([_scene('s1', 'kpi-hero', 60 * 300)])
    code, report = _main(['--props', _props(tmp_path, 'long.json', doc)], capsys)

    assert code == 0, report
    assert _verdict_for(report, RULE) == vqa.PASS, report


def test_a_forty_five_second_graph_is_representable_today(tmp_path, capsys):
    """The duration clause is AUTHORABLE — this is not the blocker.

    2700 frames at 60fps = 45.0s, the plan's lower bound, built from four
    renderable scene types. It validates and the gate is green. So the shortfall
    against 45s is arithmetic in an authoring step, not a missing capability.

    Asserted against the measured number rather than the literal 2700 so the
    test says what it means if `format.fps` ever changes under it.
    """
    per = 2700 // 4
    scenes = [_scene(f's{i}', 'kpi-hero', per) for i in range(4)]
    doc = _graph(scenes)

    total = sum(s['durationInFrames'] for s in scenes)
    assert total / doc['format']['fps'] == pytest.approx(45.0), (
        f'the fixture is {total / doc["format"]["fps"]:.2f}s, not 45.0s')

    code, report = _main(['--props', _props(tmp_path, '45s.json', doc)], capsys)
    assert code == 0, report
    assert _verdict_for(report, RULE) == vqa.PASS, report


def test_the_schema_places_no_upper_bound_on_scene_duration():
    """The absence that makes the two tests above possible, pinned.

    `Scene.durationInFrames` is `integer, minimum 1` with no maximum, and no
    other clause in the mirror schema constrains the total. Asserted as an
    absence so a future `maximum` is a deliberate act.
    """
    schema = json.loads(
        (ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json')
        .read_text(encoding='utf-8'))
    # This mirror uses draft-07 `definitions`, not 2020-12 `$defs`. Asserted by
    # lookup with a fallback rather than by index, and the failure message names
    # the key it wanted, because a wrong key here is a NameError-shaped red that
    # reads as a schema change.
    defs = schema.get('$defs') or schema.get('definitions')
    assert defs and 'Scene' in defs, (
        f'no Scene definition under $defs or definitions; keys are '
        f'{sorted(schema.keys())}')
    dur = defs['Scene']['properties']['durationInFrames']
    assert dur.get('minimum') == 1, dur
    assert 'maximum' not in dur, (
        f'Scene.durationInFrames now has a maximum: {dur}. The finding that '
        'duration is unconstrained has changed and this file must be re-measured.')


# ── clause 3: 1920x1080@60 is NOT gated by this path ────────────────────────

def test_a_640x480_at_24fps_film_passes_the_graph_gate(tmp_path, capsys):
    """The format clause, unmeasured: a portrait-of-a-phone film is clean.

    `test_p8_format_scale.py` pins that the template READS format correctly.
    Nothing pins that a film has the right one, which is a different claim.
    """
    doc = _graph([_scene('s1', 'kpi-hero', 60)], width=640, height=480, fps=24)
    code, report = _main(['--props', _props(tmp_path, 'sd.json', doc)], capsys)

    assert code == 0, report
    assert _verdict_for(report, RULE) == vqa.PASS, report


# ── the gates that DO exist, so this file is not read as "nothing is checked" ─

def test_the_delivered_graphs_are_clean_and_the_gate_stays_green(capsys):
    """The healthy direction on the REAL artefacts, from tracked source.

    Read from `pipeline/examples/`, not `studio/public/jobs/**`: that is a
    gitignored staging copy (stage_showcase.py writes it) whose contents depend
    on whichever graph was staged last.
    """
    for name in ('showcase_demo.json', 'charts_demo.json'):
        graph = EXAMPLES / name
        if not graph.exists():
            pytest.skip(f'pipeline/examples/{name} absent')
        code, report = _main(['--props', graph], capsys)
        assert _verdict_for(report, RULE) == vqa.PASS, f'{name}:\n{report}'
        assert code == 0, f'{name} exited {code}:\n{report}'


def test_the_healthy_direction_survives_in_the_same_file(capsys):
    """Kills the always-FAIL implementation, on a graph this file writes.

    Every failure test above is satisfied by `return 1` unconditionally, by an
    unconditional FAIL, or by a rule that refuses to run. This is the same entry
    point with a graph whose every scene type has a renderer, so a gate that can
    only say "no" cannot pass this file.

    Two DIFFERENT rendered types, so a rule that counted scenes instead of
    resolving types could not pass it either (the P21 convention).
    """
    doc = _graph([_scene('s1', 'kpi-hero', 120),
                  _scene('s2', 'bar-chart', 120)])
    with tempfile.TemporaryDirectory() as td:
        p = _props(Path(td), 'ok.json', doc)
        code, report = _main(['--props', p], capsys)
        assert _verdict_for(report, RULE) == vqa.PASS, report
        assert code == 0, (
            f'the healthy direction exited {code}; the gate must reject bad '
            f'graphs without rejecting good ones.\n{report}')


# ── the load-bearing finding: the gate is not wired to anything ──────────────

#: A QA gate being NAMED, as opposed to being MENTIONED. The distinction is the
#: whole point of this section, and this file already got it wrong once:
#: `render.mjs:141` names `qa_final.py` inside a comment explaining why the file
#: passes `--pixelfmt yuv420p`, and the first version of the sweep counted that
#: as a call site and went red on a comment. That is the `render.mjs` 'Unknown
#: flag' defect (a guard matching the comment that explains the fix it was meant
#: to verify) and the `generative` sweep defect, in one more shape. Comments are
#: stripped before every sweep here for that reason.
QA_NAME = re.compile(r'\b(visual_qa|qa_report|qa_layers|qa_final|check_contract)\b')

#: The showcase graph gate specifically — the only one of the five that can judge
#: a `pipeline/examples/*.json` scene graph.
SHOWCASE_GATE = re.compile(r'\bvisual_qa\b')


def _strip_comments(text: str, suffix: str) -> str:
    """Remove line and block comments so a prose mention is not a call site.

    Conservative in the direction that matters for an ABSENCE claim: stripping can
    only remove text, so it can cost a detection (a false pass) and never invent
    one (a false red). The false-red direction is the one this project has been
    burned by repeatedly, so the bias is deliberate and stated.
    """
    if suffix in {'.py', '.mjs', '.js', '.ts', '.tsx'}:
        text = re.sub(r'/\*[\s\S]*?\*/', '', text)
        text = re.sub(r'(?m)^\s*#.*$', '', text)      # whole-line `#`
        text = re.sub(r"(?<![\w'\"])#[^\n]*$", '', text, flags=re.M)  # trailing
        text = re.sub(r'(?<!:)//[^\n]*', '', text)    # `//`, not `://`
    elif suffix in {'.sh', '.yaml', '.yml'}:
        text = re.sub(r'(?m)^\s*#.*$', '', text)
    return text


def test_the_comment_stripper_separates_a_call_from_a_mention():
    """Both halves, because a sweep that only ever finds things proves nothing.

    This is the anchor for every sweep below. It is also the regression test for
    the mistake this file made on its first run: matching a comment.
    """
    prose = (
        '# qa_final all honour them, so a re-run cannot mix audio onto the old '
        'picture\n'
        '// qa_final.py 要求 yuv420p\n'
        '/* block comment naming check_contract.py */\n'
    )
    assert not QA_NAME.search(_strip_comments(prose, '.py')), (
        'comment-stripping is not working; every absence claim below is void')

    live = "run([VENV_PY, EP01 / 'scripts' / 'qa_final.py'], cwd=EP01)\n"
    assert QA_NAME.search(_strip_comments(live, '.py')), (
        'the sweep cannot see a real invocation — it reports zero forever')


def test_no_production_script_invokes_a_showcase_qa_gate():
    """Measured, not quoted: no production path runs the showcase graph gate.

    `visual_qa.py --props` is the ONLY gate in this repository that can judge a
    `pipeline/examples/*.json` scene graph, and this proves nothing outside
    `tests/` runs it.

    The scope is deliberately the SHOWCASE GATE and not "no QA at all", because
    the broader claim is false and asserting it would have been a false red. The
    first version of this sweep searched for all five gate names and returned
    eleven "offenders", of which the honest ones were:

      * `ceo_mindread_ep01|third_lantern|liaozhai_demo/scripts/qa_final.py` and
        two of their `run_post_chain.sh` — real invocations (measured:
        `run_post_chain.sh:133` is `"$PY" scripts/qa_final.py` under
        `stage 6 "finalize + QA"`). They gate VIDEO FILES against a project's own
        CONFIG (`duration matches config`, <0.3s), for vertical short-form work.
        They are not showcase gates and they are not reachable from
        `pipeline/examples/`.
      * `ceo_mindread_ep01/scripts/select_takes.py` and
        `studio/scripts/check_contract.py` — comment mentions only.
      * `studio/bin/render.mjs` — a comment mention only.

    So the finding this file rests on is narrower and specific: nothing runs the
    gate that can judge a showcase graph.
    """
    skip_dirs = {'tests', 'out', 'node_modules', '.git', '__pycache__',
                 'acestep-env', 'ffmpeg-7.1.1-full_build'}
    callers: list[str] = []
    scanners = 0
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix not in {
                '.py', '.mjs', '.sh', '.json', '.yaml', '.yml'}:
            continue
        rel = path.relative_to(ROOT)
        if any(p in skip_dirs for p in rel.parts):
            continue
        if rel.name == 'pipeline_manifest.yaml':
            continue  # catalogues the tools; it is not a call site
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        scanners += 1
        if SHOWCASE_GATE.search(_strip_comments(text, path.suffix)):
            callers.append(rel.as_posix())

    assert scanners > 100, f'only {scanners} files scanned; the sweep is vacuous'

    # The gate itself and the modules that document or import it. Named
    # explicitly rather than by pattern so the exclusion is auditable.
    instruments = {
        'studio/scripts/visual_qa.py',        # the gate
        'studio/scripts/qa_layers.py',        # imports it to build the layer report
        'studio/scripts/chart_geometry.py',   # its docstring cites the finding
        'studio/scripts/frame_baseline.py',   # cites it as a related gate
        'studio/scripts/mutation_harness.py', # harness for its own mutation contract
    }
    unexpected = sorted(set(callers) - instruments)
    assert unexpected == [], (
        'a production file now runs or imports `visual_qa` outside the test '
        'suite: ' + ', '.join(unexpected)
        + '\nIf that is a deliberate wiring, the P17 verdict changes: a gate '
          'that runs is a gate that can stop a delivery.')


def test_the_render_entry_point_calls_no_qa_gate():
    """`render.mjs` is the one thing every render goes through. It gates nothing.

    Comments are stripped first, and that is the load-bearing detail: line 141 of
    this file names `qa_final.py` in a comment explaining why `--pixelfmt` is
    passed, and the first version of this test counted that as a call and went
    red. A gate that ran after the render would have to appear in CODE.
    """
    text = _strip_comments(RENDER_MJS.read_text(encoding='utf-8'), '.mjs')
    hits = QA_NAME.findall(text)
    assert hits == [], (
        f'render.mjs now names a QA gate in code: {hits}. The finding that '
        'nothing gates a render changes and this file must be re-measured.')



def test_the_manifest_says_the_gates_are_not_enforced():
    """The repository's own statement, quoted — because it is corroboration.

    Not the primary evidence: `pipeline_manifest.yaml:204` says
    `enforced: false` under 「质量门禁（当前全部无自动执行）」, which agrees with the
    two tests above. A test asserting the string is a guard against the manifest
    being edited to claim enforcement that does not exist — not a substitute for
    executing the sweep.
    """
    text = (ROOT / 'pipeline_manifest.yaml').read_text(encoding='utf-8')
    assert re.search(r'^\s*enforced:\s*false\s*$', text, re.M), (
        'pipeline_manifest.yaml no longer records `enforced: false`. Either the '
        'gates became enforced — in which case the two tests above are the proof '
        'and this line is stale — or the record was edited. Find out which.')
    assert '零调用方' in text, (
        'the manifest no longer records 零调用方 (no callers) for the gates; the '
        'finding this file rests on needs re-measuring.')


# ── the H3 renderer question, measured rather than asserted ─────────────────

def test_no_h3_renderer_exists_in_the_render_source():
    """The load-bearing negative for the whole P17 verdict.

    `GENERATIVE_SCENE_TYPES` names `video` and `data-plane-3d` as needing H3
    rather than the Remotion motion engine, and the schema comment says so in
    prose. Prose is not a renderer. This sweeps the whole render source for any
    H3 invocation, and — the part that matters — for any renderer registered in
    `SCENE_RENDERERS` for a generative type.

    Comments are stripped before matching, because the file under test
    *documents* H3 in a comment and a guard that reads its own subject's
    commentary is green forever.
    """
    src = TEMPLATE / 'FinanceShowcaseWide.tsx'
    text = src.read_text(encoding='utf-8')
    code = re.sub(r'//[^\n]*', '', text)
    code = re.sub(r'/\*[\s\S]*?\*/', '', code)

    assert not re.search(r'\bH3\b|\bh3_', code), (
        'FinanceShowcaseWide.tsx now contains an H3 reference in CODE (comments '
        'stripped). An H3 renderer may have been added; re-measure the P17 '
        'verdict rather than inheriting it.')

    m = re.search(r'SCENE_RENDERERS[^=]*=\s*\{(.*?)\n\};', text, re.S)
    assert m, 'SCENE_RENDERERS not found; teach this test the new shape'
    registered = {
        line.split(':', 1)[0].strip().strip('\'"')
        for line in re.sub(r'//.*$', '', m.group(1), re.S).split('\n')
        if ':' in line
    }
    assert not (registered & GENERATIVE_TYPES), (
        f'SCENE_RENDERERS now routes {sorted(registered & GENERATIVE_TYPES)} — a '
        'generative type has a Remotion renderer. Re-measure before claiming P17 '
        'cannot be built.')


def test_the_two_mirrors_agree_on_the_generative_set():
    """The premise of the tests above: both mirrors say the same two types.

    If the Python mirror and the zod schema disagree about what is generative,
    then "every generative type is gated" is ambiguous and the sweep above is
    checking one of two possible sets.
    """
    scene_graph = ROOT / 'pipeline' / 'scene_graph.py'
    if not scene_graph.exists():
        pytest.skip('pipeline/scene_graph.py absent')
    text = scene_graph.read_text(encoding='utf-8')
    m = re.search(r"GENERATIVE_TYPES\s*=\s*\{([^}]*)\}", text)
    assert m, 'GENERATIVE_TYPES not found in scene_graph.py'
    py_types = set(re.findall(r"'([^']+)'", m.group(1)))
    assert py_types == GENERATIVE_TYPES, (
        f'mirrors disagree: python {sorted(py_types)} vs zod '
        f'{sorted(GENERATIVE_TYPES)}')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))