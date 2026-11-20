"""P41 — the VLM criterion is called, not read: three mutations must kill it.

WHAT THIS GUARDS
----------------
`vlm_critic.py` claims a VLM can be used as a QA instrument, and the claim
rests on one thing: when the model answers NO to "is this declared string on
this frame", the rule FAILS. That is the only judgement it makes. Every other
kind of check would be decoration — this project's most common finding, eleven
times over.

So this file does not assert that `qwen` appears in the source, nor that a
field is named correctly, nor that a function is defined. All three have been
tempting and all three are worthless here: a module can name the model, define
the field and be reached by nobody. Each test below CALLS the criterion, with
the model replaced by a transport that answers what the test needs, and
asserts what the rule then does with that answer.

NO OLLAMA REQUIRED, ON PURPOSE
------------------------------
Every test here runs with `transport=` supplied, or against a host that does
not exist. Nothing in this file opens a socket, loads a model or needs a GPU.
`unavailable_reason` is not even reached in the transport tests — it is
replaced at the same seam. A guard that needs a 6 GB model on the machine is a
guard that is red on CI for a reason that has nothing to do with the code, and
the day someone deletes `rule_frame_shows_text` will not be the day a model is
missing.

THE THREE MUTATIONS, in the order a reader should try them:

  1. absent model -> PASS        (the project's core defect: "could not check,
                                   reported green")
  2. always pass                 (a criterion that cannot fail)
  3. ignore the expected value   (accepts any picture, so the expectation is
                                   not what is being tested)

Each is proved live in docs/P41_VLM_CRITERION.md rather than asserted here, and
this file is what they were run against.

THE ONE THING THIS FILE CANNOT DO is tell you the model reads the picture
well. That is a measurement about qwen2.5vl:7b, not about this code, and it
lives in the report. What this file pins is that IF the model answers, the
verdict follows the answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import visual_qa as vqa           # noqa: E402
import vlm_critic as vc           # noqa: E402

DOC = ROOT / 'docs' / 'P41_VLM_CRITERION.md'

#: A host nothing listens on. 127.0.0.1:1 is not a port ollama has ever bound.
DEAD_HOST = 'http://127.0.0.1:1'

CHARTS = ROOT / 'pipeline' / 'examples' / 'charts_demo.json'


def _frame(tmp_path: Path, name: str = 'f.png') -> Path:
    """A real file — `unavailable_reason` checks existence before anything else."""
    p = tmp_path / name
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
    return p


def _probe(path: Path, expected: list[str]) -> vc.FrameProbe:
    return vc.FrameProbe(frame=975, path=path, expected=expected, scene_id='c07_rank')


def _answering(yes: set[str]):
    """A transport that says YES exactly for the strings in `yes`.

    The seam matters: it stands in for the model, so a test can be about the
    RULE (what does the rule do with this answer) rather than about the model
    (can it read). The prompt text is recovered from the body so the fake still
    answers the question it was asked.
    """
    def transport(body: dict, host: str, timeout: float) -> dict:
        q = body['messages'][0]['content']
        text = q.split('"')[1]
        verdict = 'YES' if text in yes else 'NO'
        return {'message': {'content': verdict}}
    return transport


def _present(path: Path) -> vc.FrameProbe:
    """A probe whose every expected string the fake model does find."""
    return _probe(path, ['48.2M', '39.9M', '36.8M'])


# ── 1. the criterion is CALLED, and its verdict follows the answer ──────────

def test_a_frame_carrying_every_declared_string_passes(tmp_path):
    """The working direction, pinned before any negative case.

    P21's lesson: a guard that only asserts the failure direction is satisfied
    by a tool that fails on everything. So PASS is pinned here, on the same
    call the mutations will break.
    """
    p = _frame(tmp_path)
    f = vc.rule_frame_shows_text([_present(p)],
                                 transport=_answering({'48.2M', '39.9M', '36.8M'}))
    assert f.verdict == vqa.PASS, (
        f'a frame carrying all three declared strings reported '
        f'{f.verdict}: {f.detail}')
    assert f.value == 0, f'{f.value} strings reported missing; there are none.'
    assert f.trusted is True


def test_a_frame_missing_one_declared_string_fails_and_says_which(tmp_path):
    """MUTATION TARGET 3 lives in the gap between this and the next test.

    The finding must NAME the missing string and carry it as data, not only
    print it. A log line is not a product: P36's `unapplied` is the shape.
    """
    p = _frame(tmp_path)
    f = vc.rule_frame_shows_text([_present(p)],
                                 transport=_answering({'48.2M', '36.8M'}))
    assert f.verdict == vqa.FAIL, (
        f'a frame WITHOUT 39.9M reported {f.verdict}. The model said NO and '
        f'that must become a FAIL — this is the one judgement the rule makes.')
    assert f.value == 1, f'expected exactly one missing string, got {f.value}'
    missing = f.extra['missing']
    assert [m['text'] for m in missing] == ['39.9M'], (
        f'the finding must name the absent string so a caller can act on it, '
        f'got {[m["text"] for m in missing]}')
    assert missing[0]['image'] == p.name and missing[0]['frame'] == 975
    assert '39.9M' in f.detail, f'the reason must be in the return value: {f.detail!r}'
    # every probe is reported, so "what did it think was there" is answerable
    assert len(f.extra['results']) == 3


def test_an_ignored_expectation_would_be_invisible_in_that_result(tmp_path):
    """WHY the missing-string assertion above is not a formality.

    A criterion that ignores its expected value and accepts any picture
    reports PASS on the frame that HAS the strings and PASS on the frame that
    does not — so the only observable difference is in `extra`. This asserts
    the difference is actually there to be observed: two probes, same
    transport answer set, different expectations, different verdicts.

    If a future edit made `expected` unused, this goes red, because both calls
    below would return the same verdict.
    """
    p = _frame(tmp_path)
    has = vc.rule_frame_shows_text([_probe(p, ['48.2M', '39.9M'])],
                                   transport=_answering({'48.2M', '39.9M'}))
    lacks = vc.rule_frame_shows_text([_probe(p, ['48.2M', '39.9M'])],
                                     transport=_answering(set()))
    assert has.verdict == vqa.PASS
    assert lacks.verdict == vqa.FAIL
    assert has.extra['probes'] == lacks.extra['probes'] == 2


def test_the_guard_does_not_depend_on_ollama_being_reachable(monkeypatch, tmp_path):
    """THE HOST-INDEPENDENCE CLAIM, asserted rather than asserted-about.

    The whole reason this file exists is that a guard which needs a 6 GB model
    is a guard that is red on CI for a reason unrelated to the code. The first
    build of this module got that wrong in a way only a real run would show:
    `unavailable_reason` checked reachability BEFORE the transport seam, so
    pointing `VLM_CRITIC_HOST` at a closed port turned three tests of THIS
    guard red. The fix was to skip the reachability probe when a transport was
    supplied — a judge that has been replaced cannot be absent.

    So the claim is a test. If a future edit reintroduces an environment
    dependency, this goes red here rather than on someone else's machine.
    """
    # The host must be passed EXPLICITLY to the call, not left to a default:
    # `probe_text`/`ask_vlm` bind `host: str = DEFAULT_HOST` at import, so
    # patching the module attribute does not reach a default argument that was
    # already evaluated. The first version of this test patched only
    # `DEFAULT_HOST` and called without `host=`, so both calls went to the LIVE
    # ollama and it passed with the short-circuit deleted — a dead test, found
    # by mutation rather than by reading it.
    monkeypatch.setenv('VLM_CRITIC_HOST', DEAD_HOST)   # for a fresh import
    monkeypatch.setattr(vc, 'DEFAULT_HOST', DEAD_HOST)  # for this module
    p = _frame(tmp_path)
    f = vc.rule_frame_shows_text([_present(p)],
                                 transport=_answering({'48.2M', '39.9M', '36.8M'}),
                                 host=DEAD_HOST)
    assert f.verdict == vqa.PASS, (
        f'with the host unreachable and the judge replaced, the rule reported '
        f'{f.verdict}. The guard must not depend on a model being present.')
    # ...and without the replacement, that same host IS a reason.
    g = vc.rule_frame_shows_text([_present(p)], host=DEAD_HOST)
    assert g.verdict == vqa.UNAVAILABLE, (
        f'an unreachable host reported {g.verdict} once the judge was no longer '
        f'replaced; the two must not be the same code path.')


def test_the_same_string_on_one_frame_is_asked_once(tmp_path):
    """Two scenes declaring `48.2M` of the SAME picture is one question.

    The dedup is keyed on (path, normalized text) rather than on the probe, so
    it cannot merge two probes that happen to share a value — a naive key on
    `text` alone would answer one frame's question and credit it to another,
    which is the P21 defect of two call sites holding one value. Asserted on
    both sides: the merge happens, and the frames do not.
    """
    a = _frame(tmp_path, 'a.png')
    b = _frame(tmp_path, 'b.png')
    t = _answering({'48.2M'})

    same_frame = vc.rule_frame_shows_text(
        [vc.FrameProbe(900, a, ['48.2M'], 'c07'), vc.FrameProbe(950, a, ['48.2M'], 'c08')],
        transport=t)
    assert same_frame.extra['probes'] == 1, (
        f'the same string on the same frame was asked {same_frame.extra["probes"]} '
        f'times; it is one question.')

    two_frames = vc.rule_frame_shows_text(
        [vc.FrameProbe(900, a, ['48.2M'], 'c07'), vc.FrameProbe(900, b, ['48.2M'], 'c07')],
        transport=t)
    assert two_frames.extra['probes'] == 2, (
        'the same string on TWO DIFFERENT frames was merged into one question. '
        'That would let one frame answer for another — the exact shape of a '
        'dedup key that is too coarse.')


# ── 2. MUTATION 1 — an absent judge must be UNAVAILABLE, never PASS ────────

def test_a_missing_frame_is_unavailable_and_never_a_pass(tmp_path):
    """The model's absence, in its cheapest form: the picture is not there."""
    f = vc.rule_frame_shows_text([_probe(tmp_path / 'absent.png', ['48.2M'])])
    assert f.verdict == vqa.UNAVAILABLE, (
        f'a frame that does not exist reported {f.verdict}. This is the '
        f'project\'s core defect — "could not check, reported green".')
    assert f.verdict != vqa.PASS
    assert f.trusted is False
    assert 'does not exist' in f.detail


def test_a_dead_host_is_unavailable_with_the_reason_attached():
    """The real shape of mutation 1: `ollama` is not running.

    One refused connection to a closed port, and the assertion is about the
    VERDICT, not about the network.
    """
    f = vc.rule_frame_shows_text(
        [vc.FrameProbe(frame=0, path=_dead_frame(), expected=['48.2M'])],
        host=DEAD_HOST)
    assert f.verdict == vqa.UNAVAILABLE, (
        f'with no ollama running, the rule reported {f.verdict} — PASS here '
        f'is the single worst outcome this module could produce.')
    assert f.verdict != vqa.PASS
    assert 'no ollama' in f.detail.lower(), f.detail
    assert f.trusted is False


def _dead_frame() -> Path:
    """A real PNG on disk, so the failure reported is the HOST and not the file."""
    import tempfile
    d = Path(tempfile.gettempdir())
    p = d / 'p41_dead_host_frame.png'
    p.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
    return p


def test_no_path_through_the_judge_can_return_a_pass_about_an_answer_it_never_got(tmp_path):
    """Mutation 1 as a STRUCTURAL claim rather than three examples.

    It drives every way the judge can be missing and asserts the rule is
    UNAVAILABLE for each, in one place, so a new failure mode added later has
    to be added here to be believed.
    """
    p = _frame(tmp_path)

    def boom(body: dict, host: str, timeout: float) -> dict:
        raise RuntimeError('connection reset by peer')

    def garbage(body: dict, host: str, timeout: float) -> dict:
        return {'message': {'content': 'I am not sure, it depends'}}

    def empty(body: dict, host: str, timeout: float) -> dict:
        return {}

    for name, kw in (
        ('transport raises', {'transport': boom}),
        ('answer unparseable', {'transport': garbage}),
        ('answer missing', {'transport': empty}),
        ('host dead', {'host': DEAD_HOST}),
    ):
        f = vc.rule_frame_shows_text([_present(p)], **kw)
        assert f.verdict == vqa.UNAVAILABLE, (
            f'{name}: reported {f.verdict}, expected UNAVAILABLE. A judge that '
            f'failed to answer must never produce PASS.')
        assert f.trusted is False, f'{name}: a verdict from an absent judge is untrusted'


def test_an_empty_probe_set_is_unavailable_not_a_pass():
    """The vacuous shape: nothing was asked, so nothing was measured."""
    f = vc.rule_frame_shows_text([])
    assert f.verdict == vqa.UNAVAILABLE, (
        f'an empty probe set reported {f.verdict}. This is `assert True` with a '
        f'frame attached: the caller built nothing and got green.')


# ── 3. the expectation is the graph's, and the graph's formatting is real ────

def test_expected_strings_honours_show_values_false(tmp_path):
    """`c02_line` declares `showValues: false`, so its numbers are NOT printed.

    This is the `c02_line` false positive, pinned: the VLM was right and a
    Python expectation that ignored the flag would have reported a correct
    frame as FAIL.
    """
    graph = json.loads(CHARTS.read_text(encoding='utf-8'))
    scenes = {s['id']: s for s in graph['scenes']}
    assert vc.expected_strings(scenes['c02_line']) == [], (
        'c02_line declares showValues: false, so no data value belongs on its '
        'frame. If this fails, either the flag moved or the expectation is '
        'reading something the renderer does not draw.')
    assert vc.expected_strings(scenes['c01_bar']) == [
        '48.2M', '39.9M', '52.1M', '36.8M', '61.4M'], (
        'c01_bar is compact-formatted and shows its values; the expected '
        'strings are what the renderer must print, character for character.')


def test_expected_strings_reads_heat_cells_but_not_a_chart_with_no_numbers():
    """The two shapes that are not a `values` array."""
    graph = json.loads(CHARTS.read_text(encoding='utf-8'))
    scenes = {s['id']: s for s in graph['scenes']}
    cells = vc.expected_strings(scenes['c06_heatmap'])
    assert len(cells) == 18, f'c06 declares 3x6 cells with showCellValues; got {len(cells)}'
    assert '12' in cells and '95' in cells and '22' in cells
    # c10 is an int bar chart; its values are the claims and they are printed
    assert vc.expected_strings(scenes['c10_bar_long']) == [
        '31', '48', '39', '57', '44', '66', '52', '71']
    # a scene with no chart at all yields nothing, not a crash
    assert vc.expected_strings({'content': {'caption': 'hi'}}) == []


def test_the_python_formatter_matches_the_renderer_it_mirrors():
    """The mirror is pinned to the shipped `formatValue`, not to my memory of it.

    Runs the real TypeScript through tsx over a corpus covering every declared
    format and both sides of the compaction boundary. A mirror nobody checks is
    how P24's two renders came to disagree on a number while agreeing on the
    verdict, so this compares the two directly rather than asserting a list of
    expected strings that I typed.

    It is a COMPARISON, not an exit code. The first build of this check
    asserted `returncode == 0` alone, which passes as long as the script runs,
    whether or not the two formatters agree. Asserting the exit status of a
    script whose job is to print disagreements is the text-existence mistake
    wearing a subprocess.
    """
    import shutil
    import subprocess
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if npx is None:
        return  # no node: skip rather than assert a number that was not measured
    check = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'charts' \
        / 'format_value_mirror.check.ts'
    proc = subprocess.run([npx, 'tsx', str(check)], capture_output=True,
                          encoding='utf-8', errors='replace', timeout=600)
    assert proc.returncode == 0, f'the check script itself failed:\n{proc.stderr}'

    rows = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(rows) >= 150, (
        f'the corpus produced only {len(rows)} rows; a mirror checked over a '
        f'tiny corpus is a mirror checked over the easy cases.')
    disagreements = []
    for ln in rows:
        raw, fmt, ts = ln.split('\t')
        got = vc.format_value(float(raw), fmt)
        if got != ts:
            disagreements.append(
                f'formatValue({raw}, {fmt!r}): ts={ts!r} python={got!r}')
    assert not disagreements, (
        f'the Python mirror and the renderer disagree on '
        f'{len(disagreements)}/{len(rows)} cases:\n  '
        + '\n  '.join(disagreements[:10]))

    # The corpus must actually reach the compacted branch, or the agreement
    # above is agreement about small numbers and says nothing about 48.2M.
    assert any(ln.endswith('\t48.2M') for ln in rows), (
        'the corpus does not contain the one value this rule is really about '
        '(c01_bar\'s first value). Without it neither side has been compared '
        'where it matters.')


def test_reproducibility_is_asserted_not_assumed(tmp_path):
    """Requirement 2: the seed and the greedy options are what buy this.

    Two calls, same transport, must produce the same verdict for the same
    input. With `DEFAULT_OPTIONS` swapped for a sampling configuration the
    assertion below is the thing that would notice — which is why it is here
    rather than a comment in the module.
    """
    p = _frame(tmp_path)
    t = _answering({'48.2M', '39.9M', '36.8M'})
    first = vc.rule_frame_shows_text([_present(p)], transport=t)
    second = vc.rule_frame_shows_text([_present(p)], transport=t)
    assert (first.verdict, first.value) == (second.verdict, second.value)
    assert vc.DEFAULT_OPTIONS['temperature'] == 0, (
        'a VLM verdict sampled at temperature > 0 is a coin flip wearing a lab '
        'coat. The greedy options are the instrument; do not loosen them.')
    assert vc.DEFAULT_OPTIONS['top_k'] == 1
    assert vc.DEFAULT_SEED == 42


def test_parse_verdict_refuses_to_invent_an_answer():
    """The three inputs, and the two that must not become measurements."""
    assert vc.parse_verdict('YES') is True
    assert vc.parse_verdict('YES, it is visible in the second cell') is True
    assert vc.parse_verdict('NO') is False
    assert vc.parse_verdict('no') is False
    for unparseable in ('', '   ', 'maybe', 'The image shows 88', '42'):
        assert vc.parse_verdict(unparseable) is None, (
            f'{unparseable!r} must not parse as a verdict; an answer this '
            f'module cannot read is a measurement it does not have.')


def test_normalize_folds_typography_but_never_folds_a_different_number():
    """Folding must stop at the claim.

    `$48.2M` and `48.2 M` are the same string on screen; `48.2M` and `48.2`
    are different claims, and the rule's only FAIL is a missing one.
    """
    assert vc.normalize('"48.2M"') == vc.normalize('48.2 M') == vc.normalize('$48.2m')
    assert vc.normalize(' 48.2M, ') == '48.2m'
    assert vc.normalize('48.2M') != vc.normalize('48.2')
    assert vc.normalize('48.2M') != vc.normalize('39.9M')


# ── 4. the rule is NOT in the pixel suite, and says so ─────────────────────

def test_the_rule_is_not_one_of_the_frame_scoped_pixel_rules():
    """It takes a graph AND a model, so folding it into `--frame` would be wrong.

    `FRAME_SCOPED_RULES` is nine rules that decide on pixels alone. This one
    cannot: with no ollama it is UNAVAILABLE, and a `--frame` run on a machine
    without a model would then report a verdict it has no instrument for. The
    assertion is that the name is absent from the set — the same shape as P22's
    `theme_contrast` guard.
    """
    assert vc.RULE not in vqa.FRAME_SCOPED_RULES, (
        f'{vc.RULE} needs a model and a graph. Registering it as a pixel rule '
        f'makes every --frame run on a machine without ollama report a verdict '
        f'it cannot support.')
    assert vc.RULE not in vqa.UNIMPLEMENTED, (
        f'{vc.RULE} is implemented and measured; if it is listed as '
        f'unimplemented, one of the two is wrong.')


def test_the_report_records_the_measurement_the_guard_cannot_take():
    """The accuracy numbers are in a document, and the guard reads THAT.

    A VLM's reading accuracy is a fact about the model, not about this code,
    so it cannot be asserted here without loading 6 GB of weights. What the
    guard CAN hold is that the report keeps stating it — and that the report
    never claims the criterion is a quality judgement, which P17 ruled out.
    """
    text = DOC.read_text(encoding='utf-8')
    assert chr(0xFFFD) not in text, 'the report contains U+FFFD.'
    assert 'NOT' in text and 'premium' in text.lower(), (
        'P17 ruled `premium product film` undecidable. A report that mentions '
        'premium without saying it is not concluding that must not ship.')
    assert '44/44' in text, (
        'the measured accuracy (44 of 44 hand-verified probes) is the evidence '
        'this whole module rests on, and it is missing from the report.')
    assert 'UNAVAILABLE' in text, 'the report must name the absence verdict.'


def test_the_report_carries_the_open_question_rejection():
    """The negative result is as load-bearing as the positive one.

    "List every number" scored 0/12 against a faithful port, and the reason it
    was wrong is the reason the port is not shipped. A future reader who sees
    only the 44/44 will reasonably try the open question again.
    """
    text = DOC.read_text(encoding='utf-8')
    assert 'showValues' in text and '0/12' in text, (
        'the report must record that the open question was measured, scored '
        '0/12, and was wrong about the model rather than the other way round.')


# ── 5. this file cannot be neutered ────────────────────────────────────────

def test_this_file_contains_no_neutered_assertion():
    """P27's inward-facing check, repeated because the failure recurs.

    `assert True or (msg)` leaves the message and the line in place, so it
    survives review and turns every mutation below into a survivor. `True`
    parses as `ast.Constant`, never `ast.Name` — a check written against
    `ast.Name` matches nothing, and that mistake was proved by mutation in P27.
    """
    import ast
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))

    def _is_true(node) -> bool:
        return isinstance(node, ast.Constant) and node.value is True

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test
        if _is_true(test):
            offenders.append((node.lineno, 'assert True'))
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or) \
                and _is_true(test.values[0]):
            offenders.append((node.lineno, 'assert True or ...'))
    assert not offenders, (
        f'this guard asserts nothing at {offenders}. Restore the real condition.')
