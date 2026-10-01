"""showcase-v1 keeps Python and TypeScript in step (P3).

The scene graph is authored by the Director (Python side) and rendered by
Remotion (TypeScript side). If the two schemas drift, scenes fail to render in
ways that are painful to debug — so the drift itself is the test.

Run:
  python -m pytest tests/test_showcase_schema_parity.py -q
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))

import scene_graph  # noqa: E402

TS = ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts'
JSON_SCHEMA = ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json'
DEMO = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'


def _ts_scene_types() -> list[str]:
    src = TS.read_text(encoding='utf-8')
    m = re.search(r'export const SceneType = z\.enum\(\[([^\]]*)\]\)', src, re.S)
    assert m, 'could not find SceneType enum in showcase-v1.ts'
    return re.findall(r"'([a-z0-9-]+)'", m.group(1))


def _ts_camera_keys() -> list[str]:
    src = TS.read_text(encoding='utf-8')
    m = re.search(r'export const CameraSchema = z\.object\(\{(.*?)\n\}\);', src, re.S)
    assert m, 'could not find CameraSchema'
    return re.findall(r'^\s{2}(\w+):', m.group(1), re.M)


def _same_members(a, b, what: str) -> None:
    """Membership, not order.

    The contract these three lists share is "the same set of types is valid on
    every side". Order was never part of it, and asserting it made a legitimate
    reordering look like drift — which is how a parity check trains people to
    ignore it. Duplicates and length are still checked, because those ARE part
    of the contract: a duplicated entry means one side declares a type twice and
    a consumer that switches on it has two identical branches.
    """
    assert len(set(a)) == len(a), f'{what}: duplicate entries in {a}'
    assert len(set(b)) == len(b), f'{what}: duplicate entries in {b}'
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    assert not missing and not extra, (
        f'{what} drifted — only on the left: {missing}; only on the right: {extra}'
    )


def test_python_and_ts_scene_types_match():
    _same_members(_ts_scene_types(), list(scene_graph.SCENE_TYPES), 'Python vs TypeScript')


def test_json_schema_scene_types_match():
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    js = doc['definitions']['Scene']['properties']['type']['enum']
    _same_members(js, list(scene_graph.SCENE_TYPES), 'JSON Schema vs Python')


def test_camera_channels_match_across_sides():
    py = [k for k in scene_graph.CAMERA_TRACKS] + ['perspective']
    ts = _ts_camera_keys()
    assert sorted(py) == sorted(ts), f'camera channels drifted: py={sorted(py)} ts={sorted(ts)}'


def _ts_generative_types() -> list[str]:
    src = TS.read_text(encoding='utf-8')
    m = re.search(r'GENERATIVE_SCENE_TYPES\s*=\s*new Set<.*?\[(.*?)\]\)', src, re.S)
    assert m, 'GENERATIVE_SCENE_TYPES not found on the TS side'
    return re.findall(r"'([a-z0-9-]+)'", m.group(1))


def test_generative_types_are_declared_on_both_sides():
    ts_gen = set(_ts_generative_types())
    assert ts_gen == scene_graph.GENERATIVE_TYPES, (
        f'generative scene routing drifted: py={scene_graph.GENERATIVE_TYPES} ts={ts_gen}')


def test_demo_graph_loads_and_resolves():
    sc, problems = scene_graph.load_or_report(DEMO)
    assert not problems, problems
    assert sc.width == 1920 and sc.fps == 60
    resolved = sc.resolve()
    assert len(resolved) == len(sc.scenes)
    assert resolved[0].startFrame == 0
    for a, b in zip(resolved, resolved[1:]):
        assert b.startFrame == a.endFrame, 'scenes must be contiguous without overlap'


def test_beat_snap_keeps_every_start_within_half_a_frame():
    """Snapping may pull a scene slightly earlier (a whole-beat duration can be
    shorter than the requested frame count), so the old "never pulls earlier"
    invariant no longer holds. What must hold is: starts land on the grid, and
    nothing overlaps."""
    sc, _ = scene_graph.load_or_report(DEMO)
    plain = {s.id: s.startFrame for s in sc.resolve(beat_snap=False)}
    snapped = sc.resolve(beat_snap=True)
    for s in snapped:
        assert abs(s.startFrame - plain[s.id]) <= 2 * (60.0 / sc.bpm) * sc.fps, (
            f'{s.id} moved too far from its unsnapped position')
        assert sc.on_beat(s.startFrame), (
            f'{s.id} is {sc.beat_distance_frames(s.startFrame):.3f} frames off the beat')
    for a, b in zip(snapped, snapped[1:]):
        assert b.startFrame >= a.endFrame, f'{a.id} overlaps {b.id}'


def test_generative_scenes_are_routed_not_guessed():
    sc, _ = scene_graph.load_or_report(DEMO)
    assert sc.generative_scenes() == [], 'the demo graph is fully programmatic'
    kinds = {s['type'] for s in sc.scenes}
    assert kinds <= set(scene_graph.SCENE_TYPES)


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))


# --- beat drift (P3 review findings) ----------------------------------------

def _long_graph(n: int, dur: int) -> dict:
    base = json.loads(DEMO.read_text(encoding='utf-8'))
    base['scenes'] = [{'id': f's{i:02d}', 'type': 'kpi-hero',
                       'durationInFrames': dur} for i in range(n)]
    return base


def test_beat_snap_does_not_accumulate_drift():
    """The failure mode: snapping each start iteratively pushes starts forward
    whenever the nearest beat falls before the previous scene ends. 8-beat
    scenes at 60fps/126BPM drifted 0.43 frames per scene, 3.86 over ten."""
    sc, _ = scene_graph.load_or_report(DEMO)
    long = sc.__class__(project='t', width=1920, height=1080, fps=60, bpm=126,
                        scenes=[{'id': f's{i}', 'type': 'kpi-hero',
                                 'durationInFrames': 229} for i in range(10)])
    # `long`, not `sc`. The synthetic timeline is built at 126 bpm, so it has to be
    # MEASURED at 126 bpm too; `beat_distance_frames` is a method, so it uses its
    # own receiver's bpm. This used to call `sc.beat_distance_frames`, which
    # happened to agree only because the demo graph also declared 126 — so the
    # assertion was really "does 126-bpm snapping stay near the GRAPH's grid",
    # and the moment the graph's tempo became a measured 128.998 against a
    # measured track, it reported 12.9 frames of drift that had never existed.
    # Nothing about the snapping changed; the test was comparing two different
    # tempi and only passed while they coincided.
    drifts = [long.beat_distance_frames(r.startFrame)
              for r in long.resolve(beat_snap=True)]
    assert max(drifts) <= 0.5 + 1e-6, f'drift exceeded half a frame: {drifts}'
    # the specific regression: monotonic growth
    assert drifts[-1] <= 0.5 + 1e-6, 'last scene drifted — error is accumulating'


def test_beat_scenes_do_not_overlap_or_share_a_start():
    sc, _ = scene_graph.load_or_report(DEMO)
    long = sc.__class__(project='t', width=1920, height=1080, fps=60, bpm=126,
                        scenes=[{'id': f's{i}', 'type': 'kpi-hero',
                                 'durationInFrames': 229} for i in range(6)])
    resolved = long.resolve(beat_snap=True)
    starts = [r.startFrame for r in resolved]
    assert len(set(starts)) == len(starts), f'two scenes share a start: {starts}'
    for a, b in zip(resolved, resolved[1:]):
        assert b.startFrame >= a.endFrame, f'{a.id} overlaps {b.id}'


def test_drift_validator_agrees_with_resolver():
    """The validator used to re-implement the beat arithmetic and disagree
    with resolve(). It must measure resolve()'s actual output."""
    doc = _long_graph(10, 229)
    sc, _ = scene_graph.load_or_report(DEMO)
    long = sc.__class__(project='t', width=1920, height=1080, fps=60, bpm=126,
                        scenes=doc['scenes'])
    reported = scene_graph.beat_aligned_durations(doc)
    actual = [r.id for r in long.resolve(beat_snap=True)
              if long.beat_distance_frames(r.startFrame) > 0.5 + 1e-6]
    assert len(reported) == len(actual), (
        f'validator reported {len(reported)} offenders, resolver found {len(actual)}')


def test_on_beat_tolerance_is_half_a_frame_not_half_a_beat():
    """A half-BEAT tolerance (14.29 frames at 126 BPM/60fps) cannot catch
    sub-beat drift — the old assertion was structurally incapable of failing."""
    sc, _ = scene_graph.load_or_report(DEMO)
    assert sc.on_beat(0), 'frame 0 is on the beat'
    assert not sc.on_beat(8), '8 frames is a quarter-beat away, must fail a half-frame test'


# --- continuity is structural, not a rounding choice (P3 review round 2) -----

def test_beat_timeline_is_exactly_continuous():
    """start[i+1] == end[i] for every boundary, in beat mode.

    The previous version derived start and duration with different rounding
    (round / floor), which is not a bug but an inexpressible state: whenever
    frac(k*beat) >= 0.5 the two disagree by one frame — an overlap with
    `round`, a gap with `floor`. Deriving each end from the next start makes
    both unrepresentable. This assertion is what the old suite was missing;
    `startFrame >= prev.endFrame` cannot see a gap.
    """
    sc, _ = scene_graph.load_or_report(DEMO)
    r = sc.resolve(beat_snap=True)
    for a, b in zip(r, r[1:]):
        assert b.startFrame == a.endFrame, (
            f'{a.id} ends {a.endFrame} but {b.id} starts {b.startFrame} '
            f'({b.startFrame - a.endFrame:+d} frames)')


def test_continuity_holds_over_many_scenes():
    sc, _ = scene_graph.load_or_report(DEMO)
    for n, dur in ((10, 229), (12, 114), (8, 343)):
        long = sc.__class__(project='t', width=1920, height=1080, fps=60, bpm=126,
                            scenes=[{'id': f's{i}', 'type': 'kpi-hero',
                                     'durationInFrames': dur} for i in range(n)])
        r = long.resolve(beat_snap=True)
        for a, b in zip(r, r[1:]):
            assert b.startFrame == a.endFrame, (
                f'{n}x{dur}f: gap/overlap at {a.id}->{b.id}')


def test_resolved_duration_is_authoritative_and_reported():
    """Beat mode may shorten a scene; that must be visible, not silent."""
    sc, _ = scene_graph.load_or_report(DEMO)
    r = sc.resolve(beat_snap=True)
    declared = sc.totalFrames
    resolved = r[-1].endFrame
    assert resolved == sum(s.durationInFrames for s in r)
    adjusted = [s for s in r if s.adjusted]
    assert len(adjusted) == sum(1 for s in r if s.requested_frames != s.durationInFrames)
    for s in adjusted:
        # the difference is quantisation only, bounded by one beat
        assert abs(s.durationInFrames - s.requested_frames) <= (60.0 / sc.bpm) * sc.fps, (
            f'{s.id} changed by more than a beat')
    assert abs(resolved - declared) <= len(r) * (60.0 / sc.bpm) * sc.fps


def test_python_and_ts_resolve_agree():
    """The rounding fix must land on both sides identically."""
    ts = (ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts').read_text(encoding='utf-8')
    assert 'Math.round((beatCursor + beats) * b)' in ts, (
        'TS side must derive the end boundary the same way Python does, '
        'otherwise the two timelines diverge by a frame')
    assert 'Math.floor' not in ts.split('resolveScenes')[1][:1200], (
        'TS side still floors durations — that reintroduces the 1-frame gap')


# --- style bible wiring (P4 review finding) ---------------------------------
#
# The graph declared palette / typography / motionLanguage / cameraLanguage and
# the renderer ignored all of it. These guard that a graph-provided style bible
# can actually reach a scene, so P5 does not build on a split brain.

def test_style_bible_field_name_is_identical_on_both_sides():
    py = (ROOT / 'pipeline' / 'scenes_probe.txt')
    ts = (ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts').read_text(encoding='utf-8')
    js = json.loads((ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json').read_text(encoding='utf-8'))
    assert 'style_bible' in ts, 'TS schema must use the same field name as JSON Schema/Python'
    assert 'style_bible' in js['properties'], 'JSON Schema field name drifted'
    sc_src = (ROOT / 'pipeline' / 'scene_graph.py').read_text(encoding='utf-8')
    assert 'style_bible' in sc_src, 'Python loader must read the same field name'
    assert not py.exists()


def test_scenes_do_not_import_design_values_directly():
    """Scenes must read palette/type/motion through the style bible context.

    Fonts and the design-height scale stay a static import on purpose — they are
    not graph-overridable — so the check is for the design VALUES, not for any
    import from the tokens module.
    """
    design_values = ('PALETTE', 'TYPE', 'MOTION', 'SPACE', 'RADIUS', 'SHADOW', 'DEPTH')
    scene_dir = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes'
    offenders = []
    for f in sorted(scene_dir.glob('*.tsx')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.startswith('import') and 'design/tokens' in line:
                imported = [n.strip().split(' as ')[0]
                            for n in line.split('{', 1)[-1].split('}', 1)[0].split(',')]
                bad = [n for n in imported if n in design_values]
                if bad:
                    offenders.append(f'{f.name}: {bad}')
    assert not offenders, (
        f'scenes import design values instead of using the style bible: {offenders}')


def test_every_scene_uses_the_style_bible_hook():
    scene_dir = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes'
    for f in sorted(scene_dir.glob('*.tsx')):
        src = f.read_text(encoding='utf-8')
        assert 'useDesign()' in src, f'{f.name} never reads the style bible'
        assert 'design/styleBible' in src, f'{f.name} does not import the style bible' 


def test_main_template_provides_the_style_bible():
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'FinanceShowcaseWide.tsx').read_text(encoding='utf-8')
    assert 'StyleBibleProvider' in src, 'main template must publish the style bible'
    assert 'doc.style_bible' in src, 'the provider must receive the graph value, not a constant'


def test_provider_is_per_scene_not_per_film():
    """A film-level provider makes `theme` decorative.

    The provider used to wrap the whole composition, taking only the document
    style bible. Backdrop honoured `scene.theme` but the scenes did not, so a
    graph asking for premium-light got a pale background behind black windows —
    a field that looked like it worked and did not. Resolution has to happen
    where the theme is declared, so the provider must sit inside the scene loop
    and receive the SCENE's theme and style bible.
    """
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'FinanceShowcaseWide.tsx').read_text(encoding='utf-8')
    assert 'theme={scene.theme}' in src, 'provider must receive the scene theme'
    assert 'override={scene.style_bible}' in src, 'provider must receive the scene style bible'
    assert 'bible={doc.style_bible}' in src, (
        'the film-level bible is still the base — dropping it would make a '
        'document-wide palette silently stop applying'
    )
    # the provider must be inside the per-scene map, i.e. after the Sequence that
    # owns the scene, not around the resolved.map(...) that owns all of them.
    # index the JSX usage, not the import statement.
    provider = src.index('<StyleBibleProvider')
    map_call = src.index('resolved.map(')
    assert provider > map_call, 'the provider is outside the scene loop again'


def test_per_scene_style_bible_exists_on_all_three_sides():
    ts = (ROOT / 'studio' / 'src' / 'schemas' / 'showcase-v1.ts').read_text(encoding='utf-8')
    js = json.loads((ROOT / 'pipeline' / 'schemas' / 'showcase-v1.schema.json').read_text(encoding='utf-8'))
    scene_props = js['definitions']['Scene']['properties']
    assert 'style_bible' in scene_props, (
        'JSON Schema sets additionalProperties:false — without this a valid '
        'per-scene override is rejected by the schema'
    )
    scene_block = ts.split('export const SceneSchema', 1)[1].split('export const ShowcaseSchema', 1)[0]
    assert 'style_bible' in scene_block, 'zod scene schema must accept a per-scene style bible'


def test_every_theme_carries_a_full_surface():
    """A theme that only swaps the palette half-works.

    Shadows are tuned for a ground: a near-black shadow is invisible on paper
    and a paper shadow is a bruise on near-black. So a theme owns palette,
    shadow AND the depth ramp together, and the check is that all three move.
    """
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'themes.ts').read_text(encoding='utf-8')
    assert "'premium-dark'" in src and "'premium-light'" in src, 'both themes must exist'
    for section in ('palette', 'shadow', 'depthCue'):
        # once in the Theme type, and once per theme body
        assert src.count(f'{section}:') >= 3, f'{section} must exist per theme, not just in the type'


def test_scenes_do_not_hardcode_theme_colours():
    """A hex literal in a scene cannot follow a theme, by definition."""
    import re
    scene_dir = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes'
    offenders = []
    for f in sorted(scene_dir.glob('*.tsx')):
        for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if re.search(r'#[0-9A-Fa-f]{6}\b', line) and 'rgba(' not in line:
                offenders.append(f'{f.name}:{i}: {line.strip()[:70]}')
    assert not offenders, f'scenes hardcode colours instead of asking for a role: {offenders}'


# --- style bible effectiveness (P6.5) ----------------------------------------
#
# The demo graph carried a style_bible whose 15 declared keys were almost all
# inert: the palette duplicated the default dark theme, and the typography was
# CSS shorthand strings where the tokens are {size,weight,tracking,leading}
# objects, so mergeSection's type guard dropped every one of them silently.
#
# Nothing looked broken, because inert is silent. The light theme is what finally
# exposed it: the graph's dark palette overrode six keys while the theme supplied
# the rest, and premium-light rendered as a half-and-half frame. So both failure
# modes are now checked directly.

#: keys a theme owns. A document that declares one of these has opted that key
#: out of theming — which is only ever right if it means to.
THEME_OWNED_PALETTE = {
    'background', 'backgroundAlt', 'surface', 'surfaceElevated',
    'ink', 'inkMuted', 'inkFaint', 'accent', 'accentDim', 'onAccent',
    'positive', 'negative', 'grid', 'hairline', 'column', 'columnBright',
}


def test_graph_style_bible_does_not_fight_the_theme():
    for path in sorted((ROOT / 'pipeline' / 'examples').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        for scope, bible in [('document', doc.get('style_bible'))] + [
            (f"scene {s.get('id')}", s.get('style_bible'))
            for s in doc.get('scenes', [])
        ]:
            if not isinstance(bible, dict):
                continue
            palette = bible.get('palette') or {}
            clash = sorted(set(palette) & THEME_OWNED_PALETTE)
            assert not clash, (
                f'{path.name} {scope} pins theme-owned palette keys {clash}. '
                f'Themes supply these; pinning them re-creates the half-applied '
                f'theme bug (light background, dark surfaces).'
            )


def test_graph_typography_is_token_shaped_not_css_shorthand():
    """`"900 120px Bahnschrift"` cannot pass mergeSection's type guard.

    TypeRole entries are objects. A shorthand string is silently dropped, so a
    graph can look like it restyles type while changing nothing.
    """
    for path in sorted((ROOT / 'pipeline' / 'examples').glob('*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        bibles = [doc.get('style_bible')] + [s.get('style_bible') for s in doc.get('scenes', [])]
        for bible in bibles:
            if not isinstance(bible, dict):
                continue
            for role, value in (bible.get('typography') or {}).items():
                assert isinstance(value, dict), (
                    f'{path.name}: typography.{role} is {type(value).__name__}, but a '
                    f'type role is an object with size/weight/tracking/leading — a '
                    f'shorthand string here is silently ignored'
                )


def test_the_two_themes_actually_differ():
    """A theme that resolves to the same palette is a theme in name only."""
    themes = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'themes.ts').read_text(encoding='utf-8')
    dark = re.search(r"'premium-dark':\s*\{.*?palette:\s*darkPalette", themes, re.S)
    light = re.search(r"'premium-light':\s*\{.*?palette:\s*lightPalette", themes, re.S)
    assert dark and light, 'both themes must be defined'
    assert 'const darkPalette' in themes and 'const lightPalette' in themes
    # the two palettes are separate objects, not one aliased twice
    assert themes.count('background:') >= 2, 'each palette must define its own background'


def test_style_bible_merge_ignores_unknown_keys():
    """A typo in the graph must not blank or widen a token."""
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'styleBible.tsx').read_text(encoding='utf-8')
    assert 'mergeSection' in src, 'style bible must merge per known keys'
    assert 'typeof base[key]' in src, 'merge must type-check incoming values against the default'


# --- motion foundation (P5) --------------------------------------------------

def test_no_scene_hand_writes_spring_physics():
    """Scenes must name an intent (`settle`, `land`, `reveal`), not pick damping.

    Before P5, `damping: 200` appeared three times across three scenes, each
    hand-tuned, so two entrances that should have felt identical did not.
    """
    scene_dir = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes'
    offenders = []
    for f in sorted(scene_dir.glob('*.tsx')):
        for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if ('damping:' in line or 'stiffness:' in line) and 'MOTION.springs' not in line:
                offenders.append(f'{f.name}:{i}')
    assert not offenders, f'hand-written spring physics in scenes: {offenders}'


def test_motion_tokens_are_named_by_intent():
    tokens = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'tokens.ts').read_text(encoding='utf-8')
    for name in ('settle', 'pop', 'land', 'reveal', 'hero'):
        assert f'{name}:' in tokens, f'motion token {name!r} missing'
    assert 'profiles' in tokens, 'motion profiles (premium/energetic/cinematic/minimal) missing'


def test_transitions_are_frame_local():
    """A transition must not consume time from its neighbours: scene start
    frames are fixed by resolve(), so a transition that shifted them would move
    every downstream subtitle and beat off its absolute second."""
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'common' / 'primitives.tsx').read_text(encoding='utf-8')
    assert 'SceneEnter' in src, 'scene transitions must exist'
    body = src.split('export const SceneEnter')[1]
    for banned in ('Sequence', 'durationInFrames={', 'trimBefore'):
        assert banned not in body, (
            f'SceneEnter must stay inside its own frames; found {banned!r}')


def test_primitives_do_not_shadow_remotion_spring():
    """A prop called `spring` shadows remotion's spring() and turns
    `spring({...})` into calling a string. Renamed to springName after it bit us."""
    src = (ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'common' / 'primitives.tsx').read_text(encoding='utf-8')
    assert 'spring?: SpringName' not in src, 'the springName rename was reverted'
    assert 'spring as remotionSpring' in src, 'remotion spring must be imported under an alias'


def test_every_scene_calls_the_style_bible_and_a_primitive():
    scene_dir = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'scenes'
    for f in sorted(scene_dir.glob('*.tsx')):
        src = f.read_text(encoding='utf-8')
        assert 'useDesign()' in src, f'{f.name} must read design through the style bible'
        assert 'MOTION.springs' in src or 'common/primitives' in src, (
            f'{f.name} animates without the motion tokens or primitives')


# --- dual-graph drift (P6 review finding) -----------------------------------
#
# studio/public/jobs/ is gitignored because Remotion Studio serves props over
# HTTP. That makes it a place where a hand-placed copy of a tracked graph can
# drift forever without leaving a trace in any commit — which is exactly what
# happened in P6.0. The staging script plus its sidecar is the guard.

def test_staging_script_exists_and_writes_a_fingerprint_sidecar():
    s = (ROOT / 'studio' / 'scripts' / 'stage_showcase.py').read_text(encoding='utf-8')
    assert 'SIDECAR' in s, 'staging must record which source it copied from'
    assert 'fingerprint' in s, 'staging must hash the source so drift is detectable'
    assert 'sort_keys=True' in s, 'fingerprint must ignore key order / formatting'


def test_source_graphs_are_tracked():
    """The graphs a render depends on must live in git; the staging copy is a
    derived artefact, never the source of truth."""
    import subprocess
    import shutil as _sh
    git = _sh.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    tracked = subprocess.run([git, 'ls-files', 'pipeline/examples'],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    graphs = [g for g in tracked if g.endswith('.json')]
    assert graphs, 'no showcase source graph is tracked — renders would be unreproducible'


def test_staging_copy_is_not_the_render_input():
    """render.mjs must be pointed at the source graph, not the staging copy."""
    s = (ROOT / 'studio' / 'bin' / 'render.mjs').read_text(encoding='utf-8')
    assert '--props' in s, 'render.mjs takes props from the command line'
    # the staging path is where Studio keeps props; it must not be a default
    assert "default: 'jobs" not in s, 'render.mjs must not default to a staging copy'
