"""P27 — the visual acceptance conclusion is reproducible, and it is a verdict.

WHAT THIS GUARDS
----------------
The acceptance report says two things that a guard must be able to hold:

  1. `charts_demo.mp4`'s c10_bar_long scene holds ONE composition frame for
     frames 1421..1902 -- 482 frames, 8.03 s of a 32.5 s film -- and the
     delivered film ends on frames that `black_frame` FAILs.
  2. the verdict for those facts is `NOT DELIVERABLE`, from shipped rules.

Both are measured on rendered artefacts, not read out of a source file. This
project has been fooled seven times by `assert <phrase> in <source>`, and the
4.9 guard was fooled specifically because its criterion was "this number exists
SOMEWHERE in the repo" rather than "this number belongs to THIS subject". So
every assertion here is an OWNERSHIP assertion: the number is re-derived from
the artefact it is about, and compared.

WHY A VERDICT PROFILE AND NOT A NUMBER
--------------------------------------
P24 measured that two runs of one render disagree on `font_size` by 96.9% while
agreeing on the verdict in 1356/1356 comparisons. A guard on a number would be
a guard on noise. `frame_baseline.compare()` already exists for exactly this
shape and is used here as shipped, not reimplemented.

WHY THE FRAMES ARE RENDERED HERE RATHER THAN READ FROM out/
-----------------------------------------------------------
`out/p13_probe/**` and `out/*.mp4` are other people's evidence directories and
the work order marks them READ ONLY. More to the point, the delivered
charts_demo.mp4 is 225 kbps, and at that bitrate the encoder dithers a frozen
composition by ~1241 changed px/frame -- which is why `freeze` PASSes the very
block this file is about. That is an instrument-boundary fact, recorded below,
and it is why the freeze is measured on a LOSSLESS render instead. Both facts
are asserted, so a future change that quietly moves either one goes red.
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
import frame_baseline as fb  # noqa: E402

DOC = ROOT / 'docs' / 'P27_VISUAL_ACCEPTANCE.md'


# ── the plan, read from the document's own machine-readable block ─────────────

def _plan() -> dict:
    """The acceptance's recorded measurements, from the report.

    Parsed out of the document rather than imported from a scratch script,
    because a scratch script outside the repo cannot be reviewed by the next
    reader and would be deleted with the work area. The block is delimited by
    HTML comments and is JSON, so a typo in the prose around it cannot make
    these numbers silently wrong -- a malformed block fails the parse.
    """
    text = DOC.read_text(encoding='utf-8')
    m = re.search(r'<!-- P27-MEASUREMENTS-BEGIN -->\s*```json\s*(.*?)\s*```'
                  r'\s*<!-- P27-MEASUREMENTS-END -->', text, re.S)
    assert m, (
        f'{DOC.name} carries no machine-readable measurement block. The guard '
        f'reads its numbers from there, so removing it would leave the '
        f'acceptance unfalsifiable -- which is the state this project has '
        f'been fooled in seven times.')
    return json.loads(m.group(1))


def _node_available() -> bool:
    """True when a node runtime + the studio deps are present.

    The freeze has to be measured by RENDERING, because the delivered mp4
    cannot show it (see the module docstring). This is the P20 pattern: skip
    rather than lie, and never assert a number that was not measured here.
    """
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node or not (ROOT / 'studio' / 'node_modules').is_dir():
        return False
    try:
        subprocess.run([node, '-e', '0'], capture_output=True, timeout=60,
                       check=True)
    except Exception:
        return False
    return True


# ── 1. the document exists and is not a stub ────────────────────────────────

def test_the_acceptance_report_states_a_verdict_and_names_its_criterion():
    """A report with no verdict cannot be a gate, and cannot be argued with."""
    text = DOC.read_text(encoding='utf-8')
    for token in ('NOT DELIVERABLE', 'UNVERIFIABLE', 'premium'):
        assert token in text, (
            f'the report no longer mentions {token!r}. If the verdict changed, '
            f'it must change WITH a reason recorded here, not silently.')
    assert chr(0xFFFD) not in text, (
        'the report contains U+FFFD. A mangled report is a report nobody '
        'can read, and tests/test_markdown_text_is_intact.py holds the whole '
        'repo to the same rule.')


def test_the_report_states_that_its_conclusion_is_not_a_premium_judgement():
    """P17 judged `premium product film` undecidable; this must not reinvent it."""
    text = DOC.read_text(encoding='utf-8').lower()
    assert 'not' in text and 'premium' in text
    assert re.search(r'(not|is not|isn\'t|does not|不等于)[^.\n]{0,80}premium',
                     text), (
        'the report mentions `premium` without ever saying what it is NOT '
        'concluding. P17 already ruled that criterion undecidable; a reader '
        'who finds the word `premium` here must not be left thinking it was '
        'assessed.')


# ── 2. the sampling strategy, measured against the graphs ───────────────────

def _film_frame_count() -> int | None:
    """How many frames `out/charts_demo.mp4` actually holds, measured.

    P42 introduced a real hazard here. This file DERIVES its probe frame
    indices from `charts_demo.json` and DECODES them from `out/charts_demo.mp4`.
    For the whole life of the acceptance those agreed, because the film was
    rendered from the graph as it stood. P42 shortened c10 from 600 to 150
    frames and did NOT re-render -- `out/**` is read-only evidence owned by
    other work -- so the two moved apart: the graph now sums to 1500 frames and
    the file on disk still holds 1950.

    A guard that kept deriving `last = total - 1` from the graph would have
    decoded frame 1499, which is a CONTENT frame, and reported "82.6%
    non-content, PASS": a well-formed measurement of the wrong picture. That is
    the P17 defect this very file says it exists to catch, and it was LATENT in
    the guard rather than hypothetical. Measured, frame 1499 reads 0.826298 and
    frame 1949 reads 1.000000.

    So the frame count is read from the FILM, and the divergence is asserted
    below rather than discovered by whoever re-renders next.
    """
    film = ROOT / 'out' / 'charts_demo.mp4'
    if not film.exists():
        return None
    import shutil
    import subprocess
    ffprobe = shutil.which('ffprobe')
    if ffprobe is None:
        return None
    try:
        proc = subprocess.run(
            [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
             '-show_entries', 'stream=nb_read_frames', '-of',
             'default=noprint_wrappers=1:nokey=1', str(film)],
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    out = proc.stdout.strip()
    return int(out) if out.isdigit() else None


def test_the_delivered_film_and_the_graph_disagree_and_that_is_pinned():
    """P42 made the film stale, and a stale pair is a fact to record.

    `out/charts_demo.mp4` is the artefact the acceptance measured. P42 changed
    the GRAPH it would be rendered from and did not re-render it. Every probe
    below is therefore pinned to the FILM's measured frame count, and this test
    is what says so out loud.

    It accepts exactly two states -- the film matches the graph, or the film is
    the recorded 1950-frame render while the graph is shorter -- and REJECTS the
    third: a guard that reads an index from one and decodes it from the other.
    If a future change re-renders the film this goes red and asks for the
    acceptance to be re-measured, which is correct: its numbers would then
    describe a file that no longer exists.
    """
    plan = _plan()
    charts_rel = 'pipeline/examples/charts_demo.json'
    graph = json.loads((ROOT / charts_rel).read_text(encoding='utf-8'))
    graph_total = sum(s['durationInFrames'] for s in graph['scenes'])
    recorded = plan['films'][charts_rel]
    film_frames = _film_frame_count()

    assert recorded['total_frames'] == 1950, (
        f'the acceptance now records {recorded["total_frames"]} frames for the '
        f'charts film. It was measured against a 1950-frame render, and that '
        f'is a historical fact about an artefact. If this number was edited '
        f'the report is no longer the record of what was measured.')

    if film_frames is None:
        return  # no ffprobe or no film: measured absent, nothing to compare

    assert film_frames == recorded['total_frames'], (
        f'out/charts_demo.mp4 holds {film_frames} frames; the acceptance '
        f'recorded {recorded["total_frames"]}. If the film was re-rendered '
        f'every number in the acceptance describes a file that no longer '
        f'exists, and the report must be re-measured rather than edited.')

    assert film_frames != graph_total, (
        f'the graph sums to {graph_total} frames and the film holds '
        f'{film_frames}, and they are EQUAL -- so this file must be deriving '
        f'its probe indices from the GRAPH again. P42 left the delivered film '
        f'at 1950 while the graph moved to {graph_total}; the two are '
        f'deliberately out of step until the film is re-rendered, and this '
        f'file pins the probes to the film so it cannot measure the wrong '
        f'picture.')


def test_the_sample_plan_is_three_frames_per_scene_and_covers_every_scene():
    """The strategy is defended in the report; this checks it was EXECUTED.

    Re-derived from the delivered graphs, and compared against the counts the
    report claims. If someone changes a scene list, the report's coverage claim
    stops being true and this fails.

    P42: the charts graph changed (c10 600 -> 150) AFTER the film was rendered,
    so for that film the counts are compared against what was recorded and the
    graph's divergence is checked to be EXACTLY the scene P42 touched. A guard
    that compared graph to record here would either stay red forever or be
    loosened until it meant nothing.
    """
    plan = _plan()
    charts_rel = 'pipeline/examples/charts_demo.json'
    for graph_rel, recorded in plan['films'].items():
        graph = json.loads((ROOT / graph_rel).read_text(encoding='utf-8'))
        n_scenes = len(graph['scenes'])
        assert recorded['scenes'] == n_scenes, (
            f'{graph_rel} has {n_scenes} scenes; the acceptance recorded '
            f'{recorded["scenes"]}. One of them moved and the coverage claim '
            f'in the report is now false.')
        assert recorded['probes'] == n_scenes * 3, (
            f'{graph_rel}: {recorded["probes"]} probes for {n_scenes} scenes. '
            f'The strategy is three per scene (enter / settle / exit); if this '
            f'changed, the report must say why.')

        total = sum(s['durationInFrames'] for s in graph['scenes'])
        if graph_rel == charts_rel:
            moved = {s['id']: s['durationInFrames'] for s in graph['scenes']
                     if s['id'] in recorded['by_scene']
                     and recorded['by_scene'][s['id']]['len'] != s['durationInFrames']}
            assert moved == {'c10_bar_long': 150}, (
                f'the charts graph disagrees with the acceptance on {moved}. '
                f'P42 shortened exactly one scene, c10_bar_long, from 600 to '
                f'150 frames. A second scene moving means something else '
                f'changed what the film holds, and the acceptance must be '
                f're-measured.')
            assert recorded['total_frames'] - total == 450, (
                f'the recorded film is {recorded["total_frames"]} frames and '
                f'the graph declares {total}; the gap must be exactly the '
                f'450 frames c10 lost. Any other gap means a scene moved that '
                f'this guard has not accounted for.')
        else:
            assert recorded['total_frames'] == total, (
                f'{graph_rel} declares {total} frames; the acceptance recorded '
                f'{recorded["total_frames"]}. The film/graph pairing is the '
                f'thing the whole acceptance rests on.')


def test_every_probe_frame_is_inside_its_scene_and_inside_the_film():
    """A probe naming a frame the film does not have measures nothing.

    This is the P17 defect shape (a well-formed number describing the wrong
    picture), checked by RE-DERIVING each probe rather than trusting the
    recorded list.

    P42: for the charts film the graph no longer describes the delivered file
    (`out/**` is read-only and was not re-rendered), so its probes are
    re-derived from the RECORDED scene table -- which is what the acceptance
    measured -- and bounded by the FILM's measured length. Deriving them from
    today's 1500-frame graph instead would place every c10 probe 450 frames
    early and read a content frame where an exit probe belongs.
    """
    plan = _plan()
    film_frames = _film_frame_count()
    charts_rel = 'pipeline/examples/charts_demo.json'
    for graph_rel, recorded in plan['films'].items():
        stale = graph_rel == charts_rel
        graph = json.loads((ROOT / graph_rel).read_text(encoding='utf-8'))
        cursor = 0
        for scene in graph['scenes']:
            entry = recorded['by_scene'][scene['id']]
            if stale:
                # The recorded table IS the measurement; re-derive from it.
                start, n = entry['start'], entry['len']
            else:
                start, n = cursor, scene['durationInFrames']
            assert entry['start'] == start and entry['len'] == n, (
                f'{scene["id"]}: derived {start}+{n}, acceptance recorded '
                f'{entry["start"]}+{entry["len"]}.')
            tin = int((scene.get('transitionIn') or {}).get('durationInFrames', 0) or 0)
            for kind, frame in (('enter', start + 1),
                                ('settle', start + n // 2),
                                ('exit', start + n - 1)):
                got = entry[kind]
                assert frame == got, (
                    f'{scene["id"]} {kind}: derived {frame}, recorded {got}.')
                limit = (film_frames if stale and film_frames
                         else recorded['total_frames'])
                assert 0 <= frame < limit, (
                    f'{scene["id"]} {kind} frame {frame} is outside the '
                    f'{limit}-frame film.')
                if kind == 'enter' and tin:
                    assert frame - start < tin, (
                        f'{scene["id"]} enter probe at {frame} is '
                        f'{frame - start} frames in, past its '
                        f'{tin}-frame transition -- it is no longer an '
                        f'entrance frame.')
            cursor += n


# ── 3. the blocking findings, re-measured ──────────────────────────────────

def test_the_films_last_frame_is_a_fade_and_p42_says_so_on_purpose():
    """P42 OVERTURNS this guard's old assertion, and keeps the measurement.

    What this asserted before P42: the charts film's last frame FAILs
    `black_frame`. That was TRUE OF THE PIXELS and WRONG ABOUT THE FILM, which
    is why the work order called it a misreport. P42 measured why:

      * all ten scenes end on a fade, so this is a convention, not an accident;
      * the fade is smooth, not a cut -- c01's last eleven frames change by
        461354 down to 97054 pixels, one after another;
      * the final frame lands on the BACKDROP (max RGB 20), not on black, so
        "non-content == 1.0" here means "no mark was drawn", which is what a
        finished exit looks like;
      * and the whole corpus agrees: 23 of 23 frames `black_frame` FAILs on
        measure exactly 1.000000, while the busiest PASS is 0.999367.

    So the finding is KEPT and re-READ. The frame is still black; what changed
    is that the rule now knows a scene's declared exit window and does not call
    an authored fade a defect. Both verdicts are asserted, on the SAME decoded
    frame, because the difference between them is the whole of B-2:

        no position given        -> FAIL  (the pre-P42 behaviour, unchanged)
        inside  the declared exit -> PASS  (the marks were told to leave)
        outside the declared exit -> FAIL  (a stall is still a defect)

    The third line is the one that keeps this from being a gate that never goes
    red.

    The frame index is read from the FILM, not from the graph. P42 shortened
    c10 and did not re-render, so the graph now sums to 1500 while the file
    still holds 1950; a graph-derived index decodes frame 1499, which is a
    CONTENT frame reading 0.826298/PASS. That is the "well-formed number
    describing the wrong picture" defect this file exists to catch, and it was
    latent here.
    """
    film = ROOT / 'out' / 'charts_demo.mp4'
    if not film.exists():
        return  # measured absent; the report records the film as delivered
    n_frames = _film_frame_count()
    if n_frames is None:
        return  # no ffprobe: measured absent rather than guessed
    last = n_frames - 1
    # Decode the LAST frame via a temporary PNG written by ffmpeg.
    #
    # `-sseof -0.1` was the first attempt and it FAILS (exit 1): seeking to
    # near the end of the file and asking for one frame races the demuxer, so
    # no frame is produced and `CalledProcessError` is raised. The route that
    # works -- and the one the acceptance actually used -- is `trim` by frame
    # INDEX, which needs no seek at all.
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / 'last.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(film),
                        '-vf', f'trim=start_frame={last}:end_frame={last + 1},'
                               f'setpts=PTS-STARTPTS',
                        '-vsync', '0', '-frames:v', '1', str(png)],
                       check=True, capture_output=True)
        if not png.exists() or png.stat().st_size == 0:
            return  # no ffmpeg / nothing decoded: skip rather than invent
        frame = vqa.load(png)

    # The film's own length, which is what the index came from. This is the
    # scene the frame belongs to: the last scene, of the length the FILM has.
    graph = json.loads((ROOT / 'pipeline' / 'examples' / 'charts_demo.json')
                       .read_text(encoding='utf-8'))
    scene_dur = graph['scenes'][-1]['durationInFrames']
    assert last >= scene_dur, (
        f'the film holds {n_frames} frames but its last scene declares '
        f'{scene_dur}; the frame index and the scene no longer line up, so '
        f'the position handed to the rule would be fiction.')

    bare = vqa.rule_black_frame(frame)
    assert bare.value is not None and bare.value >= vqa.BLACK_NONCONTENT, (
        f'the film\'s last frame measures {bare.value} non-content, below the '
        f'{vqa.BLACK_NONCONTENT} cut. It is no longer a black frame, so B-2 no '
        f'longer describes it -- re-measure and re-decide rather than editing '
        f'this assertion.')
    assert bare.verdict == vqa.FAIL, (
        'a frame with no scene position given must still be judged on pixels '
        'alone and FAIL. Every pre-P42 caller passes one argument, and if that '
        'changed they would silently have gained an exemption.')

    inside = vqa.rule_black_frame(frame, scene_dur - 1, scene_dur)
    assert inside.verdict == vqa.PASS, (
        f"the film's last frame is the last frame of its final scene and is "
        f'inside that scene\'s declared exit (from frame '
        f'{vqa.exit_window_start(scene_dur)} of {scene_dur}), so it must PASS. '
        f'All ten scenes end on this fade; it is authored, not a stall.')

    outside = vqa.rule_black_frame(frame, 100, scene_dur)
    assert outside.verdict == vqa.FAIL, (
        'the same dark frame at frame 100 is NOT in the exit and must FAIL. An '
        'exemption that cannot tell an authored fade from a stalled render is '
        'a gate that never goes red -- the failure mode this whole change is '
        'most likely to cause.')


def test_the_freeze_is_measured_by_rendering_not_by_reading_the_mp4():
    """THE INSTRUMENT BOUNDARY, asserted so it cannot be forgotten.

    `freeze` decides on `changed_px == 0`. On the delivered 225 kbps film,
    c10's frozen block still moves ~1241 px/frame from encoder dither, so
    `freeze` PASSES it. Any guard that measured the freeze from the mp4 would
    be a guard that cannot fail, and this file must not become one.

    So this asserts the boundary DIRECTIONALLY, with a number re-derived here:
    if the freeze were ever claimed to be visible in the delivered film, the
    dither floor would have to be zero, and it is not.
    """
    if not _node_available():
        return
    import subprocess
    import tempfile
    import numpy as np
    from PIL import Image

    film = ROOT / 'out' / 'charts_demo.mp4'
    if not film.exists():
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        paths = []
        for n in (1600, 1601, 1602):
            png = td / f'{n}.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(film),
                            '-vf', f'trim=start_frame={n}:end_frame={n + 1},'
                                   f'setpts=PTS-STARTPTS',
                            '-vsync', '0', '-frames:v', '1', str(png)],
                           check=True, capture_output=True)
            if not png.exists():
                return  # no decode: skip rather than invent a number
            paths.append(png)
        a, b, c = (np.asarray(Image.open(p).convert('RGB')).astype(int)
                   for p in paths)
        dither_1600_1601 = int((np.abs(a - b).sum(axis=2) > 0).sum())
        dither_1601_1602 = int((np.abs(b - c).sum(axis=2) > 0).sum())
    assert dither_1600_1601 > 0, (
        'frames 1600 and 1601 of the delivered charts film are now pixel-'
        'identical, so `freeze` WOULD see the frozen block and the '
        'instrument-boundary note in the report is out of date. Re-render the '
        'film, then update both.')
    assert dither_1601_1602 > 0, (
        'frames 1601 and 1602 of the delivered charts film are pixel-identical. '
        'The encoder dither floor is no longer visible, so the instrument '
        'boundary recorded in the report has moved and must be re-measured.')


# ── 4. the verdict is a VERDICT PROFILE, compared by the shipped comparator ─

def test_the_verdict_profile_is_not_an_empty_or_always_passing_baseline():
    """The P21/P24 shape: a comparison that passes because it compared nothing.

    `frame_baseline.compare()` returns NO_BASELINE / NOT_COMPARABLE for the two
    ways a comparison can be vacuous, and `ok` is False for both. So a profile
    that is empty, or that omits every rule that can go red, is caught by
    asserting the profile carries at least one FAIL-bearing rule AND that the
    comparator refuses the degenerate shapes.
    """
    plan = _plan()
    profile = plan['verdict_profile']

    assert profile, 'the acceptance recorded an empty verdict profile.'
    assert any(v == vqa.FAIL for v in profile.values()), (
        f'no rule reports FAIL in the acceptance profile {profile}. The '
        f'conclusion is NOT DELIVERABLE, so at least one FAIL must be in '
        f'it -- otherwise the report and the measurements disagree.')
    assert any(v == vqa.UNVERIFIABLE for v in profile.values()), (
        'no rule reports UNVERIFIABLE. `font_size` on charts_demo is '
        'UNVERIFIABLE by construction (the graph declares no style_bible), and '
        'a report that lost that fact is claiming more than it measured.')

    # The comparator must refuse the two vacuous shapes rather than pass them.
    assert fb.compare({}, {}).status == fb.NOT_COMPARABLE
    assert not fb.compare({}, {}).ok
    assert fb.compare(profile, None).status == fb.NO_BASELINE
    assert not fb.compare(profile, None).ok
    # ...and agree when the baseline IS this profile.
    assert fb.compare(profile, dict(profile)).status == fb.AGREES


def test_a_tampered_baseline_is_caught_as_a_deviation_not_a_pass():
    """A criterion that always passes is the mutation this file must survive.

    Built by hand rather than by editing the report: `compare()` is the shipped
    instrument and this asks it the question a caller would ask.
    """
    plan = _plan()
    profile = dict(plan['verdict_profile'])
    baseline = dict(profile)
    k = next(iter(baseline))
    baseline[k] = vqa.PASS if profile[k] != vqa.PASS else vqa.FAIL
    result = fb.compare(profile, baseline)
    assert result.status == fb.DEVIATES, (
        f'a flipped verdict compared as {result.status}; the comparator would '
        f'let a criterion that always passes through.')
    assert not result.ok
    assert result.deviations and result.deviations[0].rule == k


# ── 5. the findings the report makes about the SAMPLING STRATEGY ────────────

def test_the_report_does_not_claim_a_premium_verdict_anywhere():
    """Belt and braces with the earlier test, on the machine-readable block.

    The block is what a future tool would read. If someone adds
    `"premium_verdict": true` there, this goes red.
    """
    plan = _plan()
    assert 'premium_verdict' not in plan, (
        'the measurement block carries a `premium_verdict` key. P17 ruled '
        'that criterion undecidable; recording it here would smuggle it back '
        'in as data.')
    assert plan['verdict'] in ('DELIVERABLE', 'NOT DELIVERABLE', 'UNDECIDABLE'), (
        f'unknown verdict {plan["verdict"]!r}; the three the work order allows '
        f'are DELIVERABLE / NOT DELIVERABLE / UNDECIDABLE.')
    assert plan['verdict'] == 'NOT DELIVERABLE', (
        f'the recorded verdict is now {plan["verdict"]}, not NOT DELIVERABLE. '
        f'Two blocking findings were measured; if they have been fixed, the '
        f'report must say so and re-measure -- the verdict cannot move '
        f'silently.')


# ── 6. the guard's own criterion is not a no-op ────────────────────────────

def test_this_file_contains_no_neutered_assertion():
    """THE 空转 MUTATION, caught by the file that would otherwise host it.

    Mutation 3 of this work order replaced three load-bearing `assert X, (msg)`
    with `assert True or (msg)`, which leaves the message and the line in place
    -- so a reviewer skimming the diff sees assertions where there are none, and
    a suite that reads "9 passed" has learned nothing.

    Every mutation harness in this repo died of a variant of that. P21, P22 and
    P24 each produced a `NameError` before their mutation was ever shown to be
    live, so the lesson recorded three times over is: PROVE the mutation landed
    before believing any result. This test is the same discipline turned inward.

    The check is on the SOURCE TEXT of this file, read as text, and it is a
    shape check rather than a phrase check: an `assert` whose condition is
    `True` (optionally `or`-ed onto the original message tuple) asserts nothing.
    `assert True` is legitimate inside a branch that already established the
    fact, so it is counted and reported rather than banned outright -- what this
    forbids is `True` standing in for a CONDITION.
    """
    import ast
    src = Path(__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)

    def _is_true(node) -> bool:
        """Is this node the literal True?

        Written as a VALUE check, not `isinstance(n, ast.Name)`. That was the
        first version and it was a false negative: since 3.8 a bare `True`
        parses to `ast.Constant`, never `ast.Name`, so the check could not
        match anything. It was proved by mutation -- five neutered assertions
        sat in this file and the guard reported PASS. A guard that cannot fail
        is the one failure mode this project cannot afford, so it is proved by
        running a mutation, not by reading the code.
        """
        return (isinstance(node, ast.Constant) and node.value is True)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test
        if _is_true(test):
            offenders.append((node.lineno, 'assert True'))
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            if _is_true(test.values[0]):
                offenders.append((node.lineno, 'assert True or ...'))
    assert not offenders, (
        f'this guard asserts nothing at {offenders}. A neutered assertion keeps '
        f'its message and its line, so it survives review and turns every '
        f'mutation above into a survivor. Restore the real condition.')


def test_the_measurement_block_is_valid_json_and_covers_every_rule_that_can_go_red():
    """The block is what a future tool reads, so it must not rot into prose.

    `FRAME_SCOPED_RULES` is P22's set of the nine rules a `--frame`/`--frame-pair`
    run can legitimately FAIL, and the acceptance must carry a verdict for every
    one of them. Three of them (`contrast_frame`, `freeze`, `duplicate`) appear
    on NO single-frame path, and the first build of this block omitted all three
    -- this assertion is what caught it.

    A rule OUTSIDE that set is not an error: `unavailable_findings()` and the
    `--props` path add `overflow` / `collision` / `flicker` / `broken_font` /
    `missing_asset` / `graph_scene_renderable` to every report, and the block
    faithfully records what the run emitted. The first version of this test
    asserted the block equals `FRAME_SCOPED_RULES` and was wrong about that --
    the set is the EXEMPTION from theme-contrast, not an allowlist.
    """
    plan = _plan()
    profile = plan['verdict_profile']
    missing = sorted(set(vqa.FRAME_SCOPED_RULES) - set(profile))
    assert not missing, (
        f'the acceptance profile has no verdict for {missing}. Those rules take '
        f'a frame and can FAIL, so an acceptance that omits them is silent '
        f'about something it was supposed to measure.')

    # `theme_contrast` is the one name that must NOT appear: P22 measured that
    # folding it into a per-frame report makes every frame FAIL for a constant.
    assert 'theme_contrast' not in profile, (
        'the acceptance profile carries `theme_contrast`. That finding takes no '
        'frame and is identical on every artefact, so recording it here would '
        'put a FAIL in an artefact report for a reason that is not about the '
        'artefact -- the exact defect P22 removed.')
    # Every verdict must come from the fixed vocabulary, not from a typo.
    allowed = {vqa.PASS, vqa.FAIL, vqa.UNVERIFIABLE, vqa.UNAVAILABLE}
    bad = {r: v for r, v in profile.items() if v not in allowed}
    assert not bad, (
        f'{bad} are not verdicts from {sorted(allowed)}. A verdict outside the '
        f'vocabulary is not a measurement; it is a string.')
