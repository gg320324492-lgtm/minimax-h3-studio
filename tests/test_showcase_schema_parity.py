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


def test_python_and_ts_scene_types_match():
    assert _ts_scene_types() == list(scene_graph.SCENE_TYPES), (
        'scene types drifted between Python and TypeScript; the renderer would '
        'reject scenes the Director considers valid')


def test_json_schema_scene_types_match():
    doc = json.loads(JSON_SCHEMA.read_text(encoding='utf-8'))
    js = doc['definitions']['Scene']['properties']['type']['enum']
    assert js == list(scene_graph.SCENE_TYPES), 'JSON Schema scene types drifted'


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
    drifts = [sc.beat_distance_frames(r.startFrame)
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
