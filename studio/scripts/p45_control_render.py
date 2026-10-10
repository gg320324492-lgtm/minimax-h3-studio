"""p45_control_render.py — prove a frame PRINTS its numbers, by changing one.

THE PROBLEM WITH LOOKING AT A FRAME. "Is `48.2M` on this frame?" is answered by
guessing which glyphs a reader sees, and every glyph guess is a chance to be
wrong (measured: this project's own classifier read the `6` of `36.8M` as `8`).
A proof that depends on the reader being right is not a proof.

THE CONTROL. Render the same scene twice, changing exactly one input value, and
diff the pixels. The perturbation is chosen so it CANNOT move the layout:

  * the value perturbed is index 0, which is never the maximum, so `fitDomain`
    returns the same domain, `niceTicks` returns the same ticks, and the gutter
    keeps its width;
  * the perturbation is one part in a hundred (c01: 48200000 -> 48682000), so the
    bar it belongs to moves by about 1% of its own height — a few pixels — while
    the STRING it prints changes in exactly one digit (`48.2M` -> `48.7M`).

So any difference inside that label's box is the printed number and nothing
else. If the label box does not change, the number was never drawn, whatever a
reader might think they saw. If it does change in one glyph-sized region, the
number IS drawn, and no glyph has to be identified for that to be true.

This is the P41 "is the positive class there at all" question answered by
controlling an input rather than by reading an output.

Usage:
    render_control_pairs()   # writes out/p45_vlm/control/<scene>/{a,c}_fNNNNN.png
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GRAPHS = REPO / 'pipeline' / 'examples' / 'charts_demo.json'
OUT = REPO / 'out' / 'p45_vlm'
STILL = REPO / 'studio' / 'bin' / 'still.mjs'

#: scene id -> (index perturbed, original value, perturbed value)
#: Each perturbation changes ONE DIGIT of the printed string and leaves the
#: domain maximum alone, so the only difference the two frames can carry is the
#: printed value itself.
PERTURB: dict[str, tuple[int, float, float]] = {
    'c01_bar': (0, 48200000, 48682000),      # '48.2M' -> '48.7M'
    'c05_bubble': (0, 12, 13),                # '12'    -> '13'
    'c10_bar_long': (0, 31, 32),              # '31'    -> '32'
}


def _load() -> dict:
    return json.loads(GRAPHS.read_text(encoding='utf-8'))


def _single_scene(doc: dict, scene_id: str) -> dict:
    out = {k: v for k, v in doc.items() if k != 'scenes'}
    out['scenes'] = [s for s in doc['scenes'] if s['id'] == scene_id]
    return out


def _perturbed(doc: dict, scene_id: str) -> dict:
    one = _single_scene(doc, scene_id)
    idx, before, after = PERTURB[scene_id]
    chart = one['scenes'][0]['content']['chart']
    assert chart['values'][idx] == before, (chart['values'][idx], before)
    chart['values'][idx] = after
    return one


def write_graphs() -> list[tuple[str, Path, Path]]:
    """Write the A (as declared) and C (one value perturbed) props for each scene."""
    doc = _load()
    made = []
    for scene_id in PERTURB:
        a = OUT / f'{scene_id}.json'
        c = OUT / f'{scene_id}_perturbed.json'
        a.write_bytes(json.dumps(_single_scene(doc, scene_id),
                                 ensure_ascii=False, indent=1).encode('utf-8'))
        c.write_bytes(json.dumps(_perturbed(doc, scene_id),
                                 ensure_ascii=False, indent=1).encode('utf-8'))
        made.append((scene_id, a, c))
    return made


def render(scene_id: str, frames: list[int]) -> tuple[Path, Path]:
    """Render A and C at `frames`; return the two output directories."""
    out_a = OUT / 'control' / scene_id / 'a'
    out_c = OUT / 'control' / scene_id / 'c'
    fl = ','.join(str(f) for f in frames)
    for props, dest in ((OUT / f'{scene_id}.json', out_a),
                        (OUT / f'{scene_id}_perturbed.json', out_c)):
        subprocess.run(
            ['node', str(STILL), '--comp', 'FinanceShowcaseWide',
             '--props', str(props), '--out', str(dest), '--frames', fl],
            cwd=str(REPO / 'studio'), check=True, capture_output=True)
    return out_a, out_c


if __name__ == '__main__':
    write_graphs()
    fs = [int(x) for x in (sys.argv[1:] or ['60', '96', '120'])]
    for scene_id in PERTURB:
        a, c = render(scene_id, fs)
        print(f'{scene_id}: A -> {a}\n{" " * len(scene_id)}  C -> {c}')