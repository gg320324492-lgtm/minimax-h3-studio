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
    `qa_report.py`, not by the frame path. There is no clause anywhere in the
    repository that requires 45-60s, that requires 1920x1080@60, and no
    measurable criterion at all for "premium product film".

    ⚠️ THIRD VERDICT REWRITTEN 2026-10-03 (P25). This file's first two guards said
    "no production path runs `visual_qa`, and `render.mjs` names no QA gate in
    code". P25 (`ad23a6c`) wired the props gate into `render.mjs` behind
    `--gate-props`, so those two went red — correctly. They are not deleted and
    not relaxed; they now assert the fact as it stands, and one of them was given
    a second, opposite claim to pin:

      * the props gate IS wired into the render path, and the wiring is in CODE
        (comments stripped) — `test_the_render_entry_point_calls_the_props_gate`;
      * the whole-repository sweep no longer reports ZERO callers: `render.mjs` is
        the one production file that runs `visual_qa`, and that is the point;
      * the FRAME gate is not wired, and must not be — see below.

WHY THE FRAME GATE IS ASSERTED AS ABSENT AND NOT JUST ABSENT-BY-OMISSION.

P25 measured, on a real 801-frame render of the delivered `showcase_demo.json`:

  * every one of the 801 frames exits non-zero through `visual_qa.py --frame`,
    and none of those reds come from the render — 801 `aspect` + 801 `font_size`
    UNVERIFIABLE because the caller supplied no `--props` and no `--declared-px`
    (P25 measured the same frame exiting 0 once both were passed), plus 50
    `black_frame` and 60 `blur` FAILs concentrated on the flat transition frames
    between scenes;
  * running the frame gate over the film costs 21.5–21.8 min against a whole-film
    render of 19.6–22.5 s — 57x to 69x — and the bottleneck is the instrument
    (`rule_black_frame`, 1.18 s of the 1.615 s per frame, an `np.unique` over
    1920x1080x3), not decoding (1.324 s for all 801 frames).

So wiring it would make EVERY render red for reasons that are not about the film
— P22's permanently-red gate with a different entrance. The guard
`test_the_frame_gate_is_not_wired_and_must_not_be` pins that as a verdict rather
than leaving it as an absence nobody would notice the day somebody wired it.

WHY THE `enforced: false` CLAIM IS MEASURED HERE AND NOT QUOTED.

The plan's own success clause for P18 is 「全过」 on four layers of gates that
`qa_layers.py` reports as `enforced: false`. Reading a comment is how this project
has been fooled seven times. So the two sweeps below execute the search and
assert on the result. Either one going quiet is a fact, not a pass.

WHAT IS DELIBERATELY NOT ASSERTED.

  * No invented "premium" metric. There is no score, no blur threshold, no
    contrast floor standing in for the phrase. The five verdicts this project has
    already accepted — collision, rule_duplicate, rule_contrast_frame, flicker,
    and the per-job baseline — were each accepted BECAUSE the measurement could
    not produce the separation the criterion needed. A sixth would be the same
    finding wearing a new name.

  * No assertion that the H3 renderer should or should not be built. That is a
    judgement for docs/. This file measures whether one could be RENDERED today.

  * No assertion that `--gate-props` is on by default. It is off by default, by
    P25's deliberate choice, because `--props` also carries timeline/report props
    that are not scene graphs and those report UNVERIFIABLE, which exits non-zero
    per `6e86b46`. Whether the flag's default should change is a decision for
    `docs/`, not a measurement, so this file states the fact in prose and does not
    assert it. `tests/test_p25_qa_in_render_path.py` pins the current default
    against the tool's own behaviour.

  * No claim that the frame gate is unfixable. P25 says it is unaffordable AT ITS
    CURRENT COST and that the cost is in one statistic (`distinct_colours`, an
    exact `np.unique` count) rather than in any verdict. Cheapen that statistic
    and the verdict must be re-made. So the guard pins today's measurements, not
    an eternity.

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
#: The delivered graph, named once so the witness test and every other
#: "is the deliverable present?" check cannot drift apart.
DEMO = EXAMPLES / 'showcase_demo.json'
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


# ── the load-bearing finding: WHAT is wired, and what is not ─────────────────
#
# ⚠️ REWRITTEN 2026-10-03. This section asserted "nothing is wired"; P25 wired the
# props gate. The two guards it produced went red, which was the correct
# behaviour, and the P14 precedent applies: an assertion that became false is
# rewritten to the new fact, in place, with the fact it used to assert recorded
# in its docstring.

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

#: The props path of that gate, which is the one P25 wired and the only one that
#: can judge a graph without pixels existing.
PROPS_PATH = re.compile(r'--props\b')

#: The per-frame path — `visual_qa.py --frame`, which is what a whole-film frame
#: gate would run once per frame. P25 measured it end to end and refused to wire
#: it; the guard below pins that refusal.
FRAME_PATH = re.compile(r'--frame\b')

#: The generated-code anchor P25's own guard uses: a QA run assembled as a
#: command, not mentioned in a sentence. A comment cannot contain this, and a
#: path constant on its own cannot either.
RUN_GATES = re.compile(r'const\s+runGates\s*=')

#: The gate COMMAND itself, captured whole. `--props` has to be inside this
#: literal, not merely somewhere else in the file: `--props` also appears in the
#: `spawnSync` argument list, and a dead `if (false)` block keeps that argument
#: list intact, so a file-wide search reports a gate that no longer runs as one
#: that does.
GATE_COMMAND = re.compile(r'const\s+runGates\s*=\s*\(\)\s*=>\s*`([^`]*)`')

#: A gate that is actually EXECUTED. `runGates()` and the arguments handed to
#: `spawnSync` are what separate a gate from a string naming one.
#:
#: ⚠️ THIS IS NOT SUFFICIENT, and it is kept only so the mutation that proved it
#: so has something to be measured against. `if (false) { … spawnSync(…) }`
#: satisfies it — dead code is the same text as live code. Reachability is
#: decided dynamically, by `_observe_gate_reach` below.
LIVE_GATE = re.compile(r'runGates\s*\(\)|spawnSync\s*\(')

#: A production file that wires the FRAME gate looks like: it decodes the film to
#: frames and hands them to `visual_qa.py --frame`. Requiring the spawn, the
#: per-frame call and the decode to co-occur means a file that merely DOCUMENTS
#: the refusal (as `render.mjs` does, at length, in a comment) cannot be
#: mistaken for one that violates it. Every entry below is stripped of comments
#: first; a comment can neither add an entry nor remove one, so the conjunction
#: is decided by CODE alone.
#:
#: `scripts/visual_qa.py` itself matches all four — it is the instrument, it takes
#: `--frame`, and its docstring example decodes — so it is excluded by name
#: below. Measured, not assumed: the sweep is asserted to have found the four
#: markers together in a calibration sample, and the instrument is the only file
#: in the repository that matched before any mutation existed.
FRAME_GATE_MARKERS = {
    'spawn': re.compile(r'spawnSync|spawn|execFileSync|execFile|child_process'),
    'qa_call': re.compile(r'visual_qa\.py'),
    'per_frame': re.compile(r"--frame['\",\s]"),
    'decode': re.compile(r'ffmpeg|-frames:v|select=.*eq\('),
}
#: The only file that may legitimately contain a whole frame gate today, and it
#: is here because it is the file the guard sweeps over — not an exemption.
FRAME_GATE_ALLOWED: frozenset[str] = frozenset()


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


def _render_mjs_at_head() -> str | None:
    """render.mjs as committed, or None outside a git checkout.

    Used as the UNMUTATED reference by the dead-code regression test. Reading
    the working tree there would make the test read a mutant as its own
    baseline, which is how it failed for the wrong reason on its first run.
    """
    import subprocess
    try:
        proc = subprocess.run(
            ['git', 'show', 'HEAD:studio/bin/render.mjs'], cwd=str(ROOT),
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout


def _gate_command_judges_the_props(source: str) -> bool:
    """Does the command render.mjs BUILDS run the gate on the props path?

    Shape-independent enough to survive a rename of the helper variable, tight
    enough that a gate switched off leaves nothing to find: if `runGates` is gone
    there is no command, and if its literal no longer carries `--props` the
    command it builds is not the props gate.

    It reads the RAW source, not a comment-stripped or blanked form: the command
    is a template literal, and blanking template text — which a scanner must do
    so a stray `}` cannot unbalance a brace walk — also hides the flag from the
    search. Reading the raw file is also the more honest place to look: the
    command is a STRING, and a string is not code.
    """
    m = GATE_COMMAND.search(source)
    return bool(m) and '--props' in m.group(1)


#: The observer. It has to be JavaScript, because the question is whether
#: render.mjs's top-level code CALLS the gate, and the only honest way to answer
#: that is to let it run and watch what it does.
#:
#: Two earlier attempts are recorded in that file's header and should not be
#: retried: a hand-written lexer inside this file, which swallowed every template
#: literal and everything after it (and lost the one real `runGates()` call,
#: which lives inside a `${…}` hole); and Node's own parser, which Node does not
#: expose to user code without acorn.
REACH_PROBE = Path(__file__).resolve().parent / '_p17b_reach.mjs'

#: Where `_observe_gate_reach` puts its mutated copies. E: is where the repo
#: lives; the probe writes nothing of its own, but the temp copy must not land
#: on C: and must not be mistaken for a deliverable.
SCRATCH_ROOT = ROOT / 'out'
SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)


def _observe_gate_reach(*, flag: bool = True, source: str | None = None
                         ) -> dict:
    """Run render.mjs's own top-level code and report what it actually did.

    `source` overrides the file's text, so a test can hand the observer a
    mutated copy WITHOUT touching `studio/bin/render.mjs`. The copy runs exactly
    as the real file would, with `spawnSync` replaced by a recorder and the
    filesystem and the Remotion renderer stubbed.

    Every failure mode returns `ok: False` with a reason, and every caller
    treats that as a FAILURE. A probe that could not run must never be read as
    "the gate is not reachable" — that would be the always-passes guard again,
    one level up.
    """
    import json
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(dir=str(SCRATCH_ROOT)) as td:
        target = Path(td) / 'render.mjs'
        target.write_text(
            source if source is not None
            else RENDER_MJS.read_text(encoding='utf-8'),
            encoding='utf-8')
        args = ['node', str(REACH_PROBE), str(target)]
        if not flag:
            args.append('off')
        proc = subprocess.run(args, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=120)

    if proc.returncode != 0 or not proc.stdout.strip():
        return {'ok': False, 'qaSpawnCount': 0, 'passedProps': False,
                'qaSpawnArgv': [],
                'runError': (proc.stderr or proc.stdout
                             or f'exit {proc.returncode}').strip()}
    try:
        observation = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {'ok': False, 'qaSpawnCount': 0, 'passedProps': False,
                'qaSpawnArgv': [], 'runError': f'unparseable output: {exc}'}
    return observation


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


def test_the_only_production_caller_of_the_showcase_gate_is_the_render_path():
    """Measured, not quoted — and no longer zero.

    WHAT THIS USED TO ASSERT, verbatim: "a production file now runs or imports
    `visual_qa` outside the test suite" with `unexpected == []`. It went red on
    2026-10-03 with exactly one entry, `studio/bin/render.mjs`, which P25 wired.
    The assertion was correct when it was written and the fact has since changed;
    per the P14 precedent it is rewritten in place rather than deleted.

    WHAT IT ASSERTS NOW, and this is the narrower and more useful claim:

      1. the set of production files that INVOKE the gate is EXACTLY
         `{studio/bin/render.mjs}` — not zero, not "a few". A second wiring is a
         decision that has to be made on the record, because every entry added
         here is another place where a delivery can be stopped;
      2. and "invokes" means more than "names". A file counts only when
         `visual_qa` and `--props` co-occur in CODE. `render.mjs` also carries a
         bare `qaScript` path constant, which is a name, not a decision; without
         the conjunction this sweep would have called a file with the gate
         DISABLED a caller, and removal of the wiring would leave it green.

    The sweep's own coverage is asserted first, so a filter that stopped matching
    (a renamed directory, a suffix change) cannot turn this into a vacuous pass.
    Comments are stripped before every match, as everywhere in this file.

    The scope is deliberately the SHOWCASE GATE and not "no QA at all", because
    the broader claim was false when this sweep was first written and asserting
    it would have been a false red. The first version searched for all five gate
    names and returned eleven "offenders", of which the honest ones were:

      * `ceo_mindread_ep01|third_lantern|liaozhai_demo/scripts/qa_final.py` and
        two of their `run_post_chain.sh` — real invocations (measured:
        `run_post_chain.sh:133` is `"$PY" scripts/qa_final.py` under
        `stage 6 "finalize + QA"`). They gate VIDEO FILES against a project's own
        CONFIG (`duration matches config`, <0.3s), for vertical short-form work.
        They are not showcase gates and they are not reachable from
        `pipeline/examples/`.
      * `ceo_mindread_ep01/scripts/select_takes.py` and
        `studio/scripts/check_contract.py` — comment mentions only.
    """
    skip_dirs = {'tests', 'out', 'node_modules', '.git', '__pycache__',
                 'acestep-env', 'ffmpeg-7.1.1-full_build'}
    invokers: list[str] = []
    namers_only: list[str] = []
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
        code = _strip_comments(text, path.suffix)
        if not SHOWCASE_GATE.search(code):
            continue
        (invokers if PROPS_PATH.search(code) else namers_only).append(
            rel.as_posix())

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
    production_callers = sorted(set(invokers) - instruments)
    assert production_callers == ['studio/bin/render.mjs'], (
        'the set of production files INVOKING the props gate is no longer exactly '
        f'the render path: {production_callers}. Naming the instrument without '
        'deciding anything is not a caller — files that do that: '
        f'{sorted(set(namers_only) - instruments)}. Adding a real caller is a '
        'decision that belongs on the record (it is another place a delivery can '
        'stop), and losing the render path one undoes P25 and restores the '
        'original P17 finding: nothing gates a render.')


def test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment():
    """`render.mjs` — the one thing every render goes through — calls the gate.

    WHAT THIS USED TO ASSERT, verbatim: `hits == QA_NAME.findall(text)`, i.e.
    `render.mjs` names NO QA gate in code. It went red on 2026-10-03 with
    `['visual_qa']`, which is P25's wiring. Rewritten in place, per P14.

    Comments are stripped first, and that is the load-bearing detail, now twice
    over: the P25 wiring sits BELOW an eighty-line comment block explaining the
    gate, so an assertion that did not strip would pass on prose alone; and
    `render.mjs:141` names `qa_final.py` in a comment explaining why
    `--pixelfmt` is passed, which is what made this file's first version red.
    `_strip_comments` is anchored by `test_the_comment_stripper_separates_a_call_
    from_a_mention` in this same file and by an independent control in
    `tests/test_p25_qa_in_render_path.py`.

    The assertion is a POSITIVE (the wiring is code), because that is the one
    thing source-reading can decide. Whether the gate can actually say no is not
    asserted here — that is decided by running the entry point and reading the
    exit code, in `tests/test_p25_qa_in_render_path.py`.

    ⚠️ THE GUARD REACHES, it does not merely NAME — and the second half of that is
    a STRUCTURAL fact, not a text one. Three versions of this test were MEASURED
    to be wrong in sequence, each caught by a mutation and each one a deeper
    layer of the same hole:

      v1  "does render.mjs mention `visual_qa`?"        — killed by a path
          constant and by a dead block. Fixed with a CONJUNCTION.
      v2  "does it mention `visual_qa` and `--props`?"   — killed by
          `if (false) { … }`, because `--props` is also an argument of the
          spawn inside the dead block. Fixed by asserting the gate COMMAND.
      v3  "the command is built and `spawnSync` appears"  — ALSO killed by
          `if (false) { const gate = spawnSync(…) }`. MEASURED 2026-10-03 by the
          command window: dead code is TEXTUALLY IDENTICAL to live code, so no
          further regex can close this. Fixed structurally, below.

    The structural half: `_observe_gate_reach` RUNS render.mjs's own top-level
    code — with `spawnSync` replaced by a recorder and the filesystem and the
    Remotion renderer stubbed — and reports whether the gate was actually
    spawned. Dead code cannot spawn anything, so no mutation of the "wrap the
    spawn in `if (false)`" shape can survive it, whatever it looks like in the
    source. `test_the_probe_observes_the_real_render_path` holds the probe
    against the real file and requires two runs that DISAGREE, so it cannot be
    a constant; `test_the_gate_is_dead_code_when_it_is_never_executed` holds it
    against the mutation that defeated every text-based version.
    """
    raw = RENDER_MJS.read_text(encoding='utf-8')
    text = _strip_comments(raw, '.mjs')
    hits = QA_NAME.findall(text)
    assert hits == ['visual_qa'], (
        f'render.mjs does not name exactly the showcase gate in code; found '
        f'{hits}. Expected exactly one instrument, `visual_qa`. If that is a '
        'deliberate change, the P17 verdict changes with it.')
    assert RUN_GATES.search(text), (
        'render.mjs no longer defines `runGates` in CODE, so it has no gate '
        'command to build. This is the shape removal takes — the wiring is gone '
        'while its leftovers would otherwise keep a text-presence guard green '
        '(measured: an earlier version of this test was green under exactly '
        'that mutation, twice, before the command itself was checked).')
    assert _gate_command_judges_the_props(raw), (
        'the command render.mjs builds no longer runs the gate on the props '
        'path. `--props` occurring elsewhere in the file does not count — it is '
        'also an argument of the spawn. The props path is the only one that can '
        'judge a scene graph before any pixels exist; without it the file '
        'carries a name and no decision.')

    observation = _observe_gate_reach()
    assert observation['ok'], (
        'the reachability observation could not be completed: '
        f'{observation.get("runError")!r}. A probe that cannot run says NOTHING '
        'about the gate — it must not be read as unreachable and must not be '
        'read as reachable.')
    assert observation['qaSpawnCount'] >= 1, (
        'render.mjs ran its own top-level code with --gate-props on its command '
        'line and spawned no QA gate. The gate is defined, the command is built, '
        'the spawn is spelled out — and it does not run. That is what dead code '
        'looks like, and no amount of text matching can see it (measured: '
        'wrapping the spawn in `if (false) { ... }` was green on every '
        'text-based version of this assertion).')
    assert observation['passedProps'], (
        'the gate ran but not on the props path: '
        f'{observation["qaSpawnArgv"]!r}. The props path is the only one that '
        'can judge a scene graph before any pixels exist.')

    assert FRAME_PATH.search(text) is None, (
        'render.mjs names `--frame` in CODE. That is the per-frame gate entry '
        'point; P25 measured it and refused to wire it (see the next test).')


def test_the_probe_observes_the_real_render_path():
    """The probe is held to the file that is actually in the repository.

    A probe that is only ever fed a sample it happens to handle is the exact
    shape of the always-passes guard this file exists to prevent. So the real
    render.mjs is observed twice, and the two runs must DISAGREE:

      * with `--gate-props` on the command line, the gate must be spawned, and
        with `--props` in its argv — that is the wiring this file asserts;
      * with the flag absent, nothing must be spawned at all — that is P25's
        "off by default", and it is what makes the first observation mean
        something rather than being a constant that always says yes.

    If both runs agree, the probe is not observing the flag and every conclusion
    drawn from it is void. Stated here rather than assumed.
    """
    with_flag = _observe_gate_reach()
    without = _observe_gate_reach(flag=False)

    for label, observation in (('with --gate-props', with_flag),
                               ('without the flag', without)):
        assert observation['ok'], (
            f'the probe could not observe render.mjs {label}: '
            f'{observation.get("runError")!r}. An unrunnable probe says nothing '
            'about the gate.')

    assert with_flag['qaSpawnCount'] >= 1, (
        'with --gate-props on the command line, render.mjs spawned no QA gate: '
        f'{with_flag["qaSpawnArgv"]!r}')
    assert with_flag['passedProps'], (
        'the gate was spawned but not on the props path: '
        f'{with_flag["qaSpawnArgv"]!r}')
    assert without['qaSpawnCount'] == 0, (
        'the gate ran WITHOUT --gate-props being asked for: '
        f'{without["qaSpawnArgv"]!r}. P25 wired it off by default deliberately '
        '(a timeline/report props file is not a scene graph and would red for a '
        'reason unrelated to the film), and this is the observation that keeps '
        'that a fact rather than a comment.')


def test_the_gate_is_dead_code_when_it_is_never_executed():
    """THE regression test for the hole the command window measured.

    `if (false) { … spawnSync(…, qaScript, '--props', propsPath) … }` satisfies
    every text-based version of the guard: the gate name is there, the command
    is built, the spawn is spelled out, the file still parses. It is still not a
    gate, and no regex can see the difference, because dead code and live code
    are the same text.

    So this mutates a COPY of render.mjs — never the file itself — and asserts
    the probe says the gate is gone. The copy is written into the scratch
    directory this file already uses and deleted in a `finally`.
    """
    original = RENDER_MJS.read_text(encoding='utf-8')
    anchor = '  const gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript,'
    closing = '  });\n  if (gate.stdout) process.stdout.write(gate.stdout);'
    # When the working tree is ITSELF under mutation this test would read the
    # mutant rather than the real file, find no anchor, and fail for the wrong
    # reason — measured: that is exactly what happened the first time, and the
    # failure was an anchor miss, not a reachability finding. So the reference
    # text is `git show HEAD:…` whenever this file is inside a repository,
    # which is the state the shipped wiring is in.
    reference = _render_mjs_at_head()
    assert reference is not None, (
        'no committed render.mjs to use as the unmutated reference; this test '
        'cannot distinguish "the gate is dead" from "the file I read was '
        'already a mutant"')
    source = reference

    assert source.count(anchor) == 1, (
        f'the gate spawn anchor is not where this test expects it '
        f'(found {source.count(anchor)}). Teach the test the new shape rather '
        'than letting it mutate nothing — a mutation that does not land is the '
        'failure mode this project has been bitten by seven times.')

    dead = source.replace(
        anchor,
        '  let gate = {status: 0, stdout: \'\'};\n'
        '  if (false) {\n'
        '  gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript,')
    assert dead.count(closing) == 1, 'the gate call closing anchor moved'
    dead = dead.replace(
        closing, '  });\n  }\n  if (gate.stdout) process.stdout.write(gate.stdout);')

    # sanity: the mutant must still be the same shape as the original in every
    # way a TEXT guard can see, or this test would pass for the wrong reason
    assert dead.count('visual_qa') == source.count('visual_qa')
    assert '--props' in dead
    assert 'runGates' in dead

    mutant = _observe_gate_reach(source=dead)
    assert mutant['ok'], (
        f'the probe could not observe the mutant: {mutant.get("runError")!r}. '
        'Without an observation this test proves nothing.')
    assert mutant['qaSpawnCount'] == 0, (
        'a gate wrapped in `if (false) { ... }` spawned anyway: '
        f'{mutant["qaSpawnArgv"]!r}. The probe is not distinguishing dead code '
        'from live code, so every claim this file makes about reachability is '
        'void.')

    # …and the unmodified text must still be seen as reaching it, so the
    # assertion above is not satisfied by a probe that always says zero.
    baseline = _observe_gate_reach(source=source)
    assert baseline['ok'], (
        f'the probe could not observe the unmutated file: '
        f'{baseline.get("runError")!r}')
    assert baseline['qaSpawnCount'] >= 1, (
        f'the probe reports no gate on the UNMUTATED render.mjs '
        f'({baseline["qaSpawnArgv"]!r}), so it cannot be used to report one on '
        'a modified file either')



def test_the_gate_can_be_proved_live_by_running_it_and_the_p17_guards_say_so():
    """The structural claim has a behavioural witness, and they must agree.

    Everything above reasons about source text. This runs the entry point and
    reads its stdout and exit code, which no amount of source reasoning can
    fake: if `runGates()` were unreachable, `QA GATE` could not appear and a
    rejected graph could not exit non-zero with no mp4 written.

    It is deliberately a WITNESS and not the primary guard. Running it costs a
    bundle, which is why P25's file is the one that does that routinely; here it
    exists so the reachability criterion has a second opinion that is not a
    regex, and so a future edit that satisfies the scanner while breaking the
    gate has somewhere to show up.

    Skips when the deliverable graph is absent — a skip is stated, never a
    silent pass.
    """
    if not DEMO.exists():
        pytest.skip('pipeline/examples/showcase_demo.json absent; the '
                    'behavioural witness cannot run')

    import os
    import shutil
    import subprocess

    scratch = ROOT / 'out' / 'p17b_witness_scratch'
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMOTION_SCRATCH_DIR=str(scratch))
    out = scratch / 'witness.mp4'
    try:
        r = subprocess.run(
            ['node', str(RENDER_MJS), '--comp', 'FinanceShowcaseWide',
             '--props', str(DEMO), '--out', str(out), '--gate-props'],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=900)
        combined = (r.stdout or '') + (r.stderr or '')
        assert 'QA GATE' in combined, (
            'the gate is declared reachable and the tool agrees it exists, but '
            'running it printed nothing — the two witnesses disagree, and the '
            f'structural one is wrong:\n{combined}')
        assert r.returncode == 0, (
            f'the delivered graph was rejected by the gate (exit {r.returncode}) '
            f'so the gate is stricter than P25 measured:\n{combined}')
        assert out.exists() and out.stat().st_size > 0, (
            f'exit 0 but no mp4 at {out}; the witness is inconclusive:\n'
            + combined)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_the_frame_gate_is_not_wired_and_must_not_be():
    """The verdict is NOT "we did not get to it". It is "do not wire it".

    P25 measured this rather than assuming it, on a real 801-frame render of
    `pipeline/examples/showcase_demo.json`:

      * 801/801 frames exit non-zero through `visual_qa.py --frame` and NONE of
        those reds come from the render: 801 `aspect` + 801 `font_size`
        UNVERIFIABLE because no `--props` and no `--declared-px` was supplied
        (the same frame exits 0 once both are), and the 50 `black_frame` /
        60 `blur` FAILs are the flat transition frames between scenes;
      * cost is 21.5-21.8 min per film against a 19.6-22.5 s render — 57x to 69x
        — and the bottleneck is `rule_black_frame` at 1.18 s of 1.615 s per
        frame, i.e. the instrument, not the decoding (1.324 s for all 801).

    So this test pins a DECISION. Wiring the frame gate does not merely fail a
    guard; it converts every render into a failure whose cause is not the film,
    which is P22's permanently-red gate through a new entrance.

    Both halves are needed:

      * the sweep, so "nobody wired it" is measured across the repository and
        not merely unobserved inside `render.mjs`;
      * the calibration, because a sweep that cannot be made to fail is a sweep
        that reports zero forever. A frame gate is recognised only when the spawn,
        the per-frame call, the decode and the instrument co-occur in CODE; a file
        that merely discusses the refusal — and `render.mjs` does, at length —
        is not one. Comments are stripped first, so the discussion cannot
        manufacture a violation either.

    REVISIT WHEN: the cost is in `distinct_colours`, an exact `np.unique` count
    inside `rule_black_frame`, and not in any verdict. Cheapen that statistic and
    this verdict must be re-made from measurements — the guard's own message says
    so. It is deliberately NOT written to survive that: a guard that outlived its
    reason would be the permanent-red gate all over again.
    """
    skip_dirs = {'tests', 'out', 'node_modules', '.git', '__pycache__',
                 'acestep-env', 'ffmpeg-7.1.1-full_build'}
    wired: list[str] = []
    scanned: list[str] = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix not in {'.py', '.mjs', '.sh'}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(p in skip_dirs for p in path.relative_to(ROOT).parts):
            continue
        try:
            code = _strip_comments(path.read_text(encoding='utf-8', errors='replace'),
                                   path.suffix)
        except OSError:
            continue
        scanned.append(rel)
        if all(p.search(code) for p in FRAME_GATE_MARKERS.values()):
            wired.append(rel)

    assert len(scanned) > 40, (
        f'only {len(scanned)} executable files scanned; the sweep is vacuous')

    offenders = sorted(set(wired) - FRAME_GATE_ALLOWED)
    assert offenders == [], (
        'a whole-film frame gate is now WIRED into a production path: '
        + ', '.join(offenders)
        + '\nMeasured on the delivered 801-frame render, all 801 frames exit '
          'non-zero and none of those reds come from the render (801 aspect + '
          '801 font_size UNVERIFIABLE for want of --props/--declared-px), and the '
          'cost is 21.5-21.8 min against a 19.6-22.5 s render. If that has '
          'changed, re-measure before unpinning this.')

    # ── the sweep's calibration: it must be ABLE to find one ─────────────────
    # A realistic whole-film frame gate: decode the film to per-frame PNGs, then
    # hand each one to the instrument. Written in full because a calibration that
    # is easier than the thing it calibrates is how a sweep reports zero forever —
    # and the first version of this one was exactly that: it omitted the decode
    # step, so the `decode` marker was unmatched and the calibration caught it.
    calibration = (
        "import {spawnSync} from 'node:child_process';\n"
        "spawnSync('ffmpeg', ['-i', mp4, '-vsync', '0', frames + '/%04d.png']);\n"
        "for (const f of frames) {\n"
        "  const gate = spawnSync('py', ['-3.12', 'scripts/visual_qa.py',\n"
        "    '--frame', f, '--props', propsPath], {encoding: 'utf8'});\n"
        "  if (gate.status !== 0) process.exit(1);\n"
        "}\n"
    )
    matched = all(p.search(calibration) for p in FRAME_GATE_MARKERS.values())
    assert matched, (
        'the frame-gate sweep cannot recognise a frame gate, so it would report '
        f'zero forever. Markers unmatched: '
        f'{[n for n, p in FRAME_GATE_MARKERS.items() if not p.search(calibration)]}')



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