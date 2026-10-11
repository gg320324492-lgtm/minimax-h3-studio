"""p48_reaccept_scenes.py — render every scene of charts_demo on demand.

P48's per-scene visual pass needs each of the ten scenes rendered STANDALONE so
a scene-local frame number is unambiguous. This is the P46 lesson restated:
`still.mjs` takes an ABSOLUTE (global) frame number, so rendering scene 8 at
"frame 100" of the full film renders a different scene -- the confident-zero
shape. A single-scene props file has scene 0 at global 0, so the frame number
IS the scene-local frame and no arithmetic can be wrong.

Two rules copied from the instruments this file leans on, both load-bearing:

  * the scratch bundle goes NEXT TO THE OUTPUT, never the system temp
    (`ab_field.py`: 125 leftover bundles, 58 GB, filled a C: drive);
  * `--public-dir` points at an EMPTY directory, because charts_demo.json
    references no static file and the default copies 773 MB of studio/public
    into every bundle.

Usage:
    py -3.12 -I p48_reaccept_scenes.py <frame> [<frame> ...]
        # each frame is scene-LOCAL, written for all ten scenes
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r'E:\Minimax-H3')
GRAPH = REPO / 'pipeline' / 'examples' / 'charts_demo.json'
OUT = REPO / 'out' / 'p48_reaccept' / 'single'
STILL = REPO / 'studio' / 'bin' / 'still.mjs'
STUDIO = REPO / 'studio'


def load() -> dict:
    return json.loads(GRAPH.read_text(encoding='utf-8'))


def single_scene(doc: dict, scene: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != 'scenes'}
    out['scenes'] = [scene]
    return out


def write_props(doc: dict, scene: dict) -> Path:
    p = OUT / f'{scene["id"]}.json'
    p.write_bytes(json.dumps(single_scene(doc, scene),
                             ensure_ascii=False, indent=1).encode('utf-8'))
    return p


def render(scene: dict, props: Path, frames: list[int]) -> Path:
    dest = OUT / scene['id']
    scratch = dest / 'scratch'
    public = dest / 'public'
    scratch.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(scratch), 'TMP': str(scratch),
           'TEMP': str(scratch), 'REMOTION_SCRATCH_DIR': str(scratch)}
    fl = ','.join(str(f) for f in frames)
    proc = subprocess.run(
        ['node', str(STILL), '--comp', 'FinanceShowcaseWide', '--props', str(props),
         '--out', str(dest), '--frames', fl, '--public-dir', str(public)],
        cwd=str(STUDIO), capture_output=True, text=True, timeout=1800,
        encoding='utf-8', errors='replace', env=env)
    if proc.returncode != 0:
        raise SystemExit(f'still failed for {scene["id"]}:\n{proc.stdout}\n{proc.stderr}')
    return dest


if __name__ == '__main__':
    frames = [int(x) for x in sys.argv[1:]] or [100]
    doc = load()
    OUT.mkdir(parents=True, exist_ok=True)
    for scene in doc['scenes']:
        props = write_props(doc, scene)
        dest = render(scene, props, frames)
        print(f'{scene["id"]:16s} {scene["type"]:20s} '
              f'frames={frames} -> {dest}')
