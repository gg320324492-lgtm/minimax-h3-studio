"""showcase-v1 loader + validator (P3).

The scene graph is the centre of the new architecture: agents author scene JSON,
not TSX. This module is the Python-side entry point — it validates, resolves the
timeline (start frames, beat snapping), and answers the questions the renderer
and the QA gates ask.

Schema: pipeline/schemas/showcase-v1.schema.json
Mirror:  studio/src/schemas/showcase-v1.ts (kept in sync by
         tests/test_showcase_schema_parity.py)

Usage:
  python pipeline/scene_graph.py --file showcase.json [--resolve] [--beat-snap]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent / 'schemas' / 'showcase-v1.schema.json'

SCENE_TYPES = (
    'video', 'kpi-hero', 'browser-window', 'browser-stack', 'dashboard',
    'stat-card', 'card-grid', 'calendar', 'bar-chart', 'line-chart',
    'area-chart', 'bubble-chart', 'rank-chart', 'slope-chart', 'heatmap',
    'data-table', 'quote', 'data-plane-3d', 'logo', 'outro',
)

# Scenes that come from H3 rather than the motion engine (P3 asset routing).
GENERATIVE_TYPES = {'video', 'data-plane-3d'}

CAMERA_TRACKS = ('translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ', 'scale', 'focus')


class ShowcaseError(ValueError):
    pass


@dataclass
class ResolvedScene:
    id: str
    type: str
    startFrame: int
    durationInFrames: int
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def endFrame(self) -> int:
        return self.startFrame + self.durationInFrames

    @property
    def generative(self) -> bool:
        """True when this scene needs H3 rather than the Remotion motion engine."""
        return self.type in GENERATIVE_TYPES


@dataclass
class Showcase:
    project: str
    width: int
    height: int
    fps: int
    bpm: float
    scenes: list[dict[str, Any]]
    style_bible: dict[str, Any] = field(default_factory=dict)

    @property
    def totalFrames(self) -> int:
        return sum(int(s['durationInFrames']) for s in self.scenes)

    def resolve(self, beat_snap: bool = False) -> list[ResolvedScene]:
        """Assign start frames.

        With beat_snap, each start snaps to the nearest beat. Note that a beat is
        a fractional number of frames at almost every (fps, bpm) pair — 126 BPM
        at 60 fps is 28.5714 frames — so no integer frame ever lands exactly on
        a beat and the tightest achievable bound is half a beat. `on_beat()`
        measures against that bound; a scene more than half a beat away means
        its duration is fighting the grid, not that the snap failed.
        """
        beat_frames = (60.0 / self.bpm) * self.fps
        out: list[ResolvedScene] = []
        cursor = 0
        for s in self.scenes:
            start = cursor
            if beat_snap and out:
                snapped = int(round(cursor / beat_frames) * beat_frames)
                # never let a snap create an overlap; a tiny forward nudge is
                # preferable to two scenes sharing a frame
                start = max(snapped, out[-1].endFrame)
            dur = int(s['durationInFrames'])
            out.append(ResolvedScene(id=s['id'], type=s['type'], startFrame=start,
                                     durationInFrames=dur, raw=s))
            cursor = start + dur
        return out

    def beat_distance_frames(self, frame: int) -> float:
        """Distance from `frame` to the nearest beat boundary, in frames."""
        beat_frames = (60.0 / self.bpm) * self.fps
        off = frame % beat_frames
        return min(off, beat_frames - off)

    def on_beat(self, frame: int) -> bool:
        """Within half a beat — the tightest bound integer frames allow."""
        return self.beat_distance_frames(frame) <= (60.0 / self.bpm) * self.fps / 2 + 1e-6

    def generative_scenes(self) -> list[ResolvedScene]:
        return [s for s in self.resolve() if s.generative]


def _validate(doc: dict) -> list[str]:
    problems: list[str] = []

    if doc.get('version') != 1:
        problems.append(f"version must be 1, got {doc.get('version')!r}")

    fmt = doc.get('format') or {}
    for k in ('width', 'height', 'fps'):
        if not isinstance(fmt.get(k), int) or fmt[k] <= 0:
            problems.append(f'format.{k} must be a positive integer')

    scenes = doc.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        problems.append('scenes must be a non-empty array')
        return problems

    seen: set[str] = set()
    cursor = 0
    for i, s in enumerate(scenes):
        sid = s.get('id', f'#{i}')
        if sid in seen:
            problems.append(f'{sid}: duplicate scene id')
        seen.add(sid)
        if s.get('type') not in SCENE_TYPES:
            problems.append(f'{sid}: unknown type {s.get("type")!r}')
        dur = s.get('durationInFrames')
        if not isinstance(dur, int) or dur < 1:
            problems.append(f'{sid}: durationInFrames must be a positive integer')
        else:
            cursor += dur

        cam = s.get('camera') or {}
        for k in CAMERA_TRACKS:
            if k in cam and not _is_track(cam[k]):
                problems.append(f'{sid}: camera.{k} must be a number or [from, to]')
        if 'perspective' in cam and not (isinstance(cam['perspective'], (int, float))
                                         and 0 < cam['perspective'] <= 20000):
            problems.append(f'{sid}: camera.perspective out of range')

        motion = s.get('motion') or {}
        if 'preset' in motion and motion['preset'] not in (
                'premium', 'energetic', 'cinematic', 'minimal'):
            problems.append(f'{sid}: motion.preset must be a known profile')

    return problems


def beat_aligned_durations(doc: dict) -> list[str]:
    """Warn when scene durations are not near a whole number of beats.

    Not fatal — a director may want an off-grid hold — but snapping only works
    if durations are multiples of the beat, otherwise the error accumulates
    across scenes. At 60 fps / 126 BPM a beat is 28.5714 frames, so use
    4/8/12-beat durations (114/229/343 frames) and the grid never drifts.
    """
    fmt = doc.get('format') or {}
    fps = fmt.get('fps')
    bpm = doc.get('bpm', 126)
    if not isinstance(fps, int) or fps <= 0:
        return []
    beat = (60.0 / float(bpm)) * fps
    out = []
    for s in doc.get('scenes') or []:
        d = s.get('durationInFrames')
        if not isinstance(d, int) or d <= 0:
            continue
        beats = d / beat
        if abs(beats - round(beats)) > 0.02:
            out.append(f'{s.get("id")}: durationInFrames={d} is {beats:.2f} beats '
                       f'(nearest whole beat: {round(beats)} → {round(round(beats) * beat)} '
                       f'frames) — beat snapping will drift')
    return out


def _is_track(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, list):
        return len(v) in (2,) and all(isinstance(x, (int, float)) for x in v)
    return False


def load(path: Path) -> Showcase:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = _validate(doc)
    if problems:
        raise ShowcaseError('; '.join(problems))
    fmt = doc['format']
    return Showcase(
        project=doc['project'],
        width=fmt['width'], height=fmt['height'], fps=fmt['fps'],
        bpm=float(doc.get('bpm', 126)),
        scenes=doc['scenes'],
        style_bible=doc.get('style_bible') or {},
    )


def load_or_report(path: Path) -> tuple[Showcase | None, list[str]]:
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = _validate(doc)
    if problems:
        return None, problems
    fmt = doc['format']
    return Showcase(project=doc['project'], width=fmt['width'], height=fmt['height'],
                    fps=fmt['fps'], bpm=float(doc.get('bpm', 126)),
                    scenes=doc['scenes'],
                    style_bible=doc.get('style_bible') or {}), []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, type=Path)
    ap.add_argument('--resolve', action='store_true', help='print the resolved timeline')
    ap.add_argument('--beat-snap', action='store_true', help='snap starts to the beat grid')
    args = ap.parse_args()

    sc, problems = load_or_report(args.file)
    if sc is None:
        print(f'{len(problems)} problem(s):')
        for p in problems:
            print(f'  ! {p}')
        return 1

    print(f'project={sc.project} {sc.width}x{sc.height}@{sc.fps} '
          f'bpm={sc.bpm} scenes={len(sc.scenes)} total={sc.totalFrames}f '
          f'({sc.totalFrames / sc.fps:.2f}s)')
    gen = sc.generative_scenes()
    if gen:
        print(f'generative (H3) scenes: {[(g.id, g.type) for g in gen]}')
    else:
        print('generative (H3) scenes: none — fully programmatic')
    if args.resolve:
        print()
        for s in sc.resolve(beat_snap=args.beat_snap):
            print(f'  {s.id:22s} {s.type:16s} {s.startFrame:5d} +{s.durationInFrames:4d} '
                  f'[{s.startFrame / sc.fps:6.2f}s]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
