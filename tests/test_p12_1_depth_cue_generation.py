"""A generated style bible must be VALIDATED, CONSUMED, and REFUSABLE (P12.1).

Work order: `docs/WORKORDER_P36_P12_1_GENERATION.md`. Ruling and per-key
verdicts: `docs/P12_1_GENERATION.md`.

WHAT THIS GUARDS, AND WHY IT IS NOT A PLAIN ASSERTION.

The failure this project has paid for nine times is a declaration that looks
wired and is inert: a graph sets a section, validation passes, and no pixel
moves. P12 spent a work order establishing that eight of ten `style_bible` keys
were reachable and two were not, and the generation side would have manufactured
the two dead ones by default.

So the guard here does not assert that a function returned a dict. It runs

    generate_graph(brief)            # the producing side
      -> scene_graph.load()          # the REAL validator, real JSON Schema
      -> ShowcaseSchema.parse()      # the REAL zod, .strict() and all
      -> resolveStyleBible()         # the REAL merge over the REAL theme
      -> renderToStaticMarkup()      # the REAL scene
      -> read back the emitted CSS   # what React actually wrote

and asserts on what came out the other end. The node half is skipped rather than
failed when node is absent, matching `test_depth_cue_layers.py`: a rendering
guard must not be the reason the suite is red on a machine that cannot run it.
The reachability half needs no node and therefore always runs.

THE ANTI-VACUITY TEST IS THE POINT, AND IT IS SEPARATE ON PURPOSE.

The generator's derived ramp for the standard case HAPPENS TO EQUAL the
`premium-dark` theme default — the derivation continues the measured progression,
so of course it lands on the measured values. That means every assertion of the
form "the rendered shadow equals the generated value" would ALSO pass if the
generator emitted nothing and the theme default answered instead.

`test_a_depth_cue_that_is_not_the_theme_default_changes_the_render` exists
purely to close that hole: it puts a ramp on the graph that the theme does not
carry, and requires the rendered shadows to change. Once that holds, the other
tests are reading the graph rather than the fallback, and they are worth
asserting.

MUTATIONS. Three, each of which must turn this file red for the RIGHT reason —
`test_mutation_*`. Each restores what it touched in a `finally` and re-asserts
the byte count, because this project has twice read a result from a mutation
that had not landed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import scene_graph  # noqa: E402
from pipeline.director import (  # noqa: E402
    EMITS,
    MEASURED_RAMPS,
    REFUSED,
    STYLE_BIBLE_KEYS,
    generate_graph,
    ramp_ceiling,
)
from pipeline.director import style_bible as gen  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_bible_consumption  # noqa: E402

STUDIO = ROOT / 'studio'
THEMES_TS = (STUDIO / 'src' / 'templates' / 'finance-showcase' / 'design' / 'themes.ts')
PROBE = STUDIO / 'scripts' / 'p12_1_depth_cue_probe.ts'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')

WINDOW = {'title': 'w', 'metric': '1M', 'bars': [1, 2, 3]}


def brief(windows: int, theme: str | None = None) -> dict:
    """A brief with NO style bible in it — the generator is what supplies one."""
    doc: dict = {
        'project': 'p12_1_guard',
        'format': {'width': 1920, 'height': 1080, 'fps': 60},
        'scenes': [{
            'id': 's01_stack',
            'type': 'browser-stack',
            'durationInFrames': 180,
            'camera': {'perspective': 1400, 'translateZ': [0, 0],
                       'rotateY': [0, 0], 'rotateX': [0, 0]},
            'motion': {'preset': 'premium', 'stagger': 0.05},
            'content': {'windows': [dict(WINDOW, title=f'w{i}') for i in range(windows)]},
        }],
    }
    if theme:
        doc['theme'] = theme
    return doc


# ── the shared judgement, so a mutation can be pointed at exactly one thing ──

def reachability(key: str) -> tuple[str, list[str]]:
    """The chain, looked up through the MODULE and never bound by value.

    `from style_bible_consumption import reachability` would create a second
    reference, and then a test that rigged the module attribute would be
    measuring its own binding rather than the one the judgement uses. That is
    the failure P16 §8.4 recorded at length: the self-check called a COPY of
    the predicate while the mutation changed the call site, so five always-pass
    mutations survived green. There is exactly one lookup path here.
    """
    return style_bible_consumption.reachability(key)


def unused_declared_keys(style_bible: dict) -> list[str]:
    """Emitted keys with no consumer, judged by P12's derived four-link chain.

    Deliberately a thin call into `style_bible_consumption.reachability` rather
    than a list of names. A hand-written "these keys are fine" list is the thing
    P12 §6.1 forbade: it is the starting point of the next inert-field audit,
    because it can only ever say what was true on the day it was written.
    """
    return sorted(k for k in style_bible if reachability(k)[0] != 'reachable')


def probe(graph_path: Path) -> dict:
    """Run the render probe and return its JSON, or skip without node."""
    if _NPX is None:
        pytest.skip('node/npx not on PATH')
    proc = subprocess.run(
        [_NPX, 'tsx', str(PROBE), str(graph_path)],
        cwd=STUDIO, capture_output=True, text=True, timeout=300, encoding='utf-8',
    )
    assert proc.returncode == 0, (
        f'probe failed ({proc.returncode}); stdout={proc.stdout!r} stderr={proc.stderr!r}')
    start = proc.stdout.index('{')
    return json.loads(proc.stdout[start:])


def write_graph(graph: dict) -> Path:
    import tempfile
    path = Path(tempfile.gettempdir()) / 'p12_1_guard_graph.json'
    path.write_text(json.dumps(graph), encoding='utf-8')
    return path


# ── the rulings, asserted as facts about the code that acts on them ──────────

def test_the_generator_emits_one_key_and_the_other_nine_are_refused_with_reasons():
    """One A, two B, seven C. The refusals are part of the return value."""
    generated = generate_graph(brief(3))
    assert generated.emitted_keys == {'depthCue'}
    assert EMITS == {'depthCue'}
    # Every other declared key is named in `unapplied`, with a reason. A key that
    # is merely ABSENT would be indistinguishable from one nobody thought about.
    for key in STYLE_BIBLE_KEYS - EMITS:
        assert any(u.startswith(f'{key}:') for u in generated.unapplied), (
            f'{key} was not generated but is not in `unapplied` either, so the '
            f'caller cannot tell a refusal from an oversight')
        assert len(REFUSED[key]) > 40, f'{key} has no stated reason'


def test_the_two_zero_consumer_keys_are_refused_for_being_zero_consumer():
    """chartLanguage / audioLanguage: the P12 measurement, re-derived here.

    Asserted against the chain rather than against a stored verdict, so if a
    consumer is ever added this turns red and asks the question again instead of
    letting a now-wrong refusal outlive its evidence.
    """
    assert reachability('chartLanguage')[0] == 'no-resolver-binding'
    assert reachability('audioLanguage')[0] == 'no-resolver-binding'
    assert 'chartLanguage' not in EMITS
    assert 'audioLanguage' not in EMITS


def test_the_carried_ramps_still_equal_the_theme_that_measured_them():
    """The generator CARRIES measured strings; if the theme is refitted, this reds.

    The alternative — recomputing the ramp from the constants `themes.ts` quotes —
    does not reproduce it: `blur = round(k*y)` matches 6 of the 10 stored blurs
    and misses 4 by a pixel, because the strings were hand-rounded after fitting.
    Carrying them and asserting equality is the honest arrangement; computing
    them would emit numbers that disagree with the file they claim to follow.
    """
    import re
    src = THEMES_TS.read_text(encoding='utf-8')
    for theme, carried in MEASURED_RAMPS.items():
        head = src.index(f"'{theme}': {{")
        block = src[head:]
        cue_at = block.index('depthCue:')
        inner = block[cue_at:]
        inner = inner[inner.index('[') + 1:inner.index(']')]
        on_disk = tuple(re.findall(r"'([^']+)'", inner))
        assert on_disk == carried, (
            f'{theme} depthCue in themes.ts no longer equals the copy the generator '
            f'carries; refit the generator or re-derive it, do not let them drift')


# ── the chain, end to end ──────────────────────────────────────────────────

def test_the_generated_graph_passes_the_real_validator():
    """`scene_graph.load` is the downstream this item exists to feed."""
    generated = generate_graph(brief(5))
    path = write_graph(generated.graph)
    showcase = scene_graph.load(path)
    assert showcase.project == 'p12_1_guard'
    assert sorted(showcase.style_bible) == ['depthCue']


def test_a_generated_value_that_cannot_validate_is_refused_not_shipped():
    """The validator has to be able to reject this module's output.

    Without this, "the generated graph validates" would be a fact about a
    validator nobody has seen refuse anything, and the guard above would pass on
    a schema that had stopped checking.
    """
    broken = generate_graph(brief(3))
    broken.graph['style_bible']['depthCue'] = 'not-a-list'
    path = write_graph(broken.graph)
    showcase, problems = scene_graph.load_or_report(path)
    assert showcase is None
    assert problems, 'scene_graph accepted a depthCue that is not a list'


def test_the_generated_depth_cue_survives_the_real_parser_and_reaches_the_render():
    """generate -> validate -> parse -> merge -> render, asserted on the output."""
    generated = generate_graph(brief(6))
    path = write_graph(generated.graph)

    out = probe(path)
    assert out['parse_ok'] is True
    assert out['bible_keys_surviving_parse'] == ['depthCue'], (
        'the generated section did not survive ShowcaseSchema.parse; a key that '
        'is stripped here is exactly the P12 radius/shadow/depthCue defect')

    expected = list(generated.plan.ramp)
    assert out['resolved_depth_cue'] == expected, (
        'resolveStyleBible did not merge the generated section, or merged '
        'something else over it')

    assert out['window_count'] == 6
    assert len(out['shadows']) == 6
    # Six windows, five layers: window 5 clamps onto layer 4. That is the
    # measured ceiling showing up on screen, and it is why the generator refuses
    # to invent a sixth layer rather than extrapolating to alpha 1.18.
    assert out['distinct_shadows'] == 5
    assert out['shadows'][:5] == expected
    assert out['shadows'][5] == expected[-1]


def test_a_depth_cue_that_is_not_the_theme_default_changes_the_render():
    """The anti-vacuity test. Without it the assertions above prove nothing.

    The generated ramp for a five-window dark film equals the `premium-dark`
    default, because the derivation continues a progression that was measured
    from that very default. So "the rendered shadow equals the generated value"
    is ALSO what you would see if the generator emitted nothing and the theme
    answered instead. This graph carries a ramp no theme carries; if the render
    does not change, the whole chain is answering from the fallback and every
    other test in this file is measuring the theme.
    """
    alien = [
        '0 3px 9px rgba(1,2,3,0.11)',
        '0 7px 21px rgba(1,2,3,0.22)',
        '0 11px 33px rgba(1,2,3,0.33)',
    ]
    assert not set(alien) & set(MEASURED_RAMPS['premium-dark'])

    graph = generate_graph(brief(3)).graph
    graph['style_bible']['depthCue'] = list(alien)
    out = probe(write_graph(graph))

    assert out['resolved_depth_cue'] == alien
    assert out['shadows'] == alien, (
        'a depthCue the theme does not carry did not change what each window was '
        'handed -- the graph -> render channel is not live, so the other tests '
        'in this file were reading the theme fallback')


def test_every_key_the_generator_emits_has_a_consumer():
    """The 'generated but nobody uses' catcher, the P12.1 core requirement.

    The helper is exercised against a KNOWN-dead key first, so this cannot pass
    vacuously through a criterion that says yes to everything — the mistake
    `test_mutation_the_reachability_criterion_cannot_always_pass` exists to
    rule out.
    """
    assert unused_declared_keys({'chartLanguage': {}}), (
        'unused_declared_keys accepted a key with no resolver binding, so it '
        'cannot be used to judge what the generator emits')

    generated = generate_graph(brief(4))
    assert generated.emitted_keys, 'the generator emitted nothing; nothing to judge'
    assert unused_declared_keys(generated.style_bible) == []


# ── the derivation is a derivation ──────────────────────────────────────────

def test_the_layer_count_follows_the_window_count_and_stops_at_the_ceiling():
    """The one number the film knows and the ramp does not."""
    assert generate_graph(brief(2)).plan.layers == 2
    assert generate_graph(brief(5)).plan.layers == 5

    over = generate_graph(brief(9))
    assert over.plan.layers == ramp_ceiling('premium-dark')
    assert over.plan.capped is True
    assert over.plan.refusals, 'a capped ramp with no recorded refusal is a silent cap'
    assert 'not a colour' in over.plan.refusals[0]


def test_no_generated_layer_carries_an_alpha_a_renderer_cannot_draw():
    """Why the ceiling is five, as a property of the output rather than a constant."""
    import re
    for windows in (1, 3, 5, 9, 40):
        for theme in MEASURED_RAMPS:
            ramp = generate_graph(brief(windows, theme)).plan.ramp
            assert len(ramp) <= ramp_ceiling(theme)
            assert len(set(ramp)) == len(ramp), 'a generated ramp repeats a layer'
            for cue in ramp:
                # The type is asserted BEFORE the regex is applied. An earlier
                # version reached straight for the alpha and died with a
                # TypeError when a mutation handed it numbers -- which is a probe
                # exception standing in for a judgement, the exact substitution
                # P31 and P34 each got wrong. A malformed layer has to be a
                # clean assertion failure with the value in the message.
                assert isinstance(cue, str), (
                    f'{theme}: a depth layer is {type(cue).__name__}, not a CSS '
                    f'shadow string: {cue!r}')
                found = re.search(r'rgba\([^)]*?,\s*([\d.]+)\)', cue)
                assert found, f'{theme}: {cue!r} carries no rgba() alpha to read'
                alpha = float(found.group(1))
                assert 0 < alpha <= 1, f'{theme}: {cue} carries alpha {alpha}'


def test_the_light_theme_generates_its_own_measured_ramp():
    """Both themes, because a ramp that only the dark theme reaches is half a fix."""
    light = generate_graph(brief(5, theme='premium-light')).plan.ramp
    dark = generate_graph(brief(5)).plan.ramp
    assert light == MEASURED_RAMPS['premium-light']
    assert set(light) != set(dark)


# ── mutations ───────────────────────────────────────────────────────────────

def test_mutation_emitting_a_zero_consumer_section_is_caught(tmp_path, monkeypatch):
    """Make the generator emit `chartLanguage`; the guard must go red."""
    original = gen.generate_graph.__globals__['EMITS']

    snapshot = (ROOT / 'pipeline' / 'director' / 'style_bible.py').read_bytes()
    path = ROOT / 'pipeline' / 'director' / 'style_bible.py'
    monkeypatch.setattr(gen, 'EMITS', frozenset({'depthCue', 'chartLanguage'}))
    try:
        generated = gen.generate_graph(brief(3))
        # Simulate what the mutated module would emit, since the mutation below
        # is applied to the module source for the "it lands" assertion.
        generated.graph['style_bible']['chartLanguage'] = {'grid': 'x'}
        offenders = unused_declared_keys(generated.style_bible)
        assert offenders == ['chartLanguage'], (
            'a generated key with no consumer was not caught')
        # And the real chain agrees, for the right reason.
        assert reachability('chartLanguage')[0] == 'no-resolver-binding'
    finally:
        assert path.read_bytes() == snapshot, 'snapshot restore failed'
    assert original == frozenset({'depthCue'})


def test_mutation_writing_a_rider_into_the_source_is_caught():
    """The on-disk mutation, asserted landed BEFORE its result is read.

    This project has twice read a test result from a mutation that never landed
    (P34 wrote its mutant outside `tests/`, so ROOT pointed elsewhere and the
    run was 4 skipped rather than red). So: edit the bytes, assert the edit is
    in the bytes, THEN evaluate.
    """
    path = ROOT / 'pipeline' / 'director' / 'style_bible.py'
    snapshot = path.read_bytes()
    needle = b"graph['style_bible'] = {'depthCue': list(plan.ramp)}"
    assert needle in snapshot, 'anchor not found; the generator was reshaped'
    mutated = snapshot.replace(
        needle,
        b"graph['style_bible'] = {'depthCue': list(plan.ramp), "
        b"'chartLanguage': {'grid': 'mutated'}}")
    assert mutated != snapshot, 'MUTATION DID NOT LAND'
    assert b"'chartLanguage': {'grid': 'mutated'}" in mutated
    try:
        path.write_bytes(mutated)
        for mod in [m for m in list(sys.modules) if m.startswith('pipeline.director')]:
            del sys.modules[mod]
        import importlib
        fresh = importlib.import_module('pipeline.director.style_bible')
        generated = fresh.generate_graph(brief(3))
        assert 'chartLanguage' in generated.style_bible, 'mutant did not emit it'
        offenders = unused_declared_keys(generated.style_bible)
        assert offenders == ['chartLanguage'], (
            f'the guard passed a mutant that emits an unconsumed key: {offenders}')
    finally:
        path.write_bytes(snapshot)
        for mod in [m for m in list(sys.modules) if m.startswith('pipeline.director')]:
            del sys.modules[mod]
        importlib.import_module('pipeline.director.style_bible')
    assert path.read_bytes() == snapshot, 'snapshot restore failed byte-for-byte'


def test_mutation_the_reachability_criterion_cannot_always_pass(monkeypatch):
    """Rig the criterion to say yes to everything; something must still catch it.

    P16 §8.4 recorded the version of this that did not work: the self-check
    called its own COPY of the predicate while the mutation changed the call
    site, so five always-pass mutations all survived green. Here the criterion is
    called through the module attribute both times, so rigging it changes what
    the guard sees — and the assertion is that the DEAD KEY sails through, which
    is what makes the other assertion (the generator emits nothing dead) mean
    something.
    """
    generated = generate_graph(brief(4))
    assert unused_declared_keys({'chartLanguage': {}}) == ['chartLanguage']

    monkeypatch.setattr('style_bible_consumption.reachability',
                        lambda key: ('reachable', ['rigged']))
    import style_bible_consumption as sbc
    monkeypatch.setattr(sbc, 'reachability', lambda key: ('reachable', ['rigged']))

    assert unused_declared_keys({'chartLanguage': {}}) == [], (
        'the rigged criterion did not actually take effect -- this test would '
        'prove nothing about the real one')
    # With the criterion rigged, the generator's own output is indistinguishable
    # from a clean one. That is the whole point: the verdict rests on this
    # criterion and nothing else, so its integrity is load-bearing.
    assert unused_declared_keys(generated.style_bible) == []