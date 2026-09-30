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


def test_beat_snap_pushes_starts_forward_only():
    sc, _ = scene_graph.load_or_report(DEMO)
    # pair by id: snapping shifts downstream cursors, so index-wise zip compares
    # different scenes and would read as a backward move
    plain = {s.id: s.startFrame for s in sc.resolve(beat_snap=False)}
    snapped = sc.resolve(beat_snap=True)
    for s in snapped:
        assert s.startFrame >= plain[s.id], 'beat snapping must never pull a scene earlier'
    # At 60 fps a 126 BPM beat is 28.5714 frames, so no integer frame can land
    # exactly on a beat. Half a frame is the tightest tolerance a viewer can see.
    for s in snapped[1:]:
        assert sc.on_beat(s.startFrame), (
            f'{s.id} is {sc.beat_distance_frames(s.startFrame):.3f} frames off the beat')


def test_generative_scenes_are_routed_not_guessed():
    sc, _ = scene_graph.load_or_report(DEMO)
    assert sc.generative_scenes() == [], 'the demo graph is fully programmatic'
    kinds = {s['type'] for s in sc.scenes}
    assert kinds <= set(scene_graph.SCENE_TYPES)


if __name__ == '__main__':
    raise SystemExit(__import__('pytest').main([__file__, '-q']))
