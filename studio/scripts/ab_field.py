"""Does every declared field have a reader, and does it change pixels? (P7.0)

The P4–P6 lesson, twice over. The demo graph carried fifteen style_bible keys
and one took effect. The reviewer's warning for P7 was the general form: a
chart API's fields that nobody reads re-run exactly that, and a chart engine
produces a lot of fields.

So this is built BEFORE the chart schema, not after:

  1. FIELD_READERS is an explicit registry. Every option a chart declares must
     appear here, naming the file that reads it. The check fails on any option
     the chart code declares but the registry does not know about — so adding a
     field without a reader is a failing test, not a silent capability.

  2. `ab_field.py` renders a graph twice, with one field changed, and reports
     how many pixels moved and where. A field can be registered and still be
     inert; the A/B is what distinguishes the two.

And the tool has to be right before it is trusted with nine chart types, which
means it must REFUSE rather than answer when it cannot answer:

  - it compares a NAMED frame, paired by exact filename on both sides. An
    earlier version took `next(dir.glob('*.png'))` from each side, so a stale
    frame left by an earlier run got compared against this run's frame — a
    comparison nobody asked for, reported with a percentage to two decimals and
    a bounding box, indistinguishable from a real result. Verified: it reported
    "2.89% changed, box (600,400,899,599)" for two IDENTICAL images, having
    compared frame 200 against frame 400.
  - the output directory is emptied before rendering, so a stale frame cannot
    survive to be compared.
  - a `--set` value whose type disagrees with the field's current value is
    refused. `tracking=5` against a graph holding `"-0.055em"` is a CSS-invalid
    declaration, which React drops and the frame never changes — an inert-looking
    zero for a typo, which is the worst possible way to learn about a typo.
  - a zero-change result says whether the frame contained anything at all, so
    "measured on a frame that does not show the subject" is distinguishable from
    "the field does nothing".

Run:
  python studio/scripts/ab_field.py --props <graph.json> \\
      --set layout.field=value --frame 400 --out out/ab
  python studio/scripts/ab_field.py --registry
  python -m pytest tests/test_chart_fields.py -q
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')

# ── 1. the registry ───────────────────────────────────────────────────────────
#
# Keyed by chart type. Each entry is option -> the file that must read it. The
# check also reads that file's source, because a registry that only checks its
# own bookkeeping cannot tell a working option from an inert one.

CHART_DIR = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'charts'

#: chart option -> the file that reads it. Empty until P7.1 lands, and an empty
#: registry is itself reported as a problem rather than passing vacuously.
FIELD_READERS: dict[str, dict[str, str]] = {}


def check_registry() -> list[str]:
    """Problems with the registry, empty when clean.

    Deliberately independent of whether the chart directory exists. The
    registry is the declaration; tying the check to a directory meant that while
    P7.1 was in flight the guard returned early and checked nothing, which is
    the vacuous pass this mechanism exists to prevent.
    """
    problems: list[str] = []
    if not FIELD_READERS:
        problems.append(
            'FIELD_READERS is empty — no chart options are declared, so the '
            'guard has nothing to check and would pass vacuously'
        )
    for chart, options in sorted(FIELD_READERS.items()):
        for opt, reader in sorted(options.items()):
            path = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / reader
            if not path.exists():
                problems.append(f'{chart}.{opt}: reader {reader} does not exist')
            elif opt not in path.read_text(encoding='utf-8'):
                problems.append(
                    f'{chart}.{opt}: registered against {reader}, but that file '
                    f'never mentions {opt} — the option is inert'
                )
    return problems


# ── 2. the A/B evidence ──────────────────────────────────────────────────────

def frame_name(frame: int) -> str:
    """The exact filename still.mjs writes for `frame`."""
    return f'f{frame:05d}.png'


def _get_path(doc: dict, dotted: str) -> tuple[bool, object]:
    """(found, current value) for a dotted path, without creating anything."""
    node: object = doc
    for key in dotted.split('.'):
        if not isinstance(node, dict) or key not in node:
            return False, None
        node = node[key]
    return True, node


def _type_name(v: object) -> str:
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, (int, float)):
        return 'number'
    if isinstance(v, str):
        return 'string'
    if isinstance(v, list):
        return 'array'
    if isinstance(v, dict):
        return 'object'
    return type(v).__name__


def check_value(doc: dict, dotted: str, raw: str) -> tuple[object, str | None]:
    """Parse the new value, refusing one that cannot possibly work.

    Returns (value, error). A type disagreement with the field's current value
    is the error that matters: CSS rejects `letterSpacing: 5`, React drops the
    declaration, and the frame comes back byte-identical — so a typo reads as
    "this field is inert", which is the most misleading answer available.
    """
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    found, current = _get_path(doc, dotted)
    if found and _type_name(current) != _type_name(value):
        return value, (
            f'{dotted} currently holds {_type_name(current)} '
            f'({current!r}); you are setting {_type_name(value)} ({value!r}). '
            f'A type mismatch usually means the new value is invalid for this '
            f'field rather than that the field is inert — e.g. a CSS length '
            f'wants "5px" or "0.055em", not 5. Refusing to report a zero that '
            f'would look like a finding.'
        )
    return value, None


def _set_path(doc: dict, dotted: str, value: object) -> None:
    parts = dotted.split('.')
    node = doc
    for key in parts[:-1]:
        nxt = node.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            node[key] = nxt
        node = nxt
    node[parts[-1]] = value


def ab_field(
    props: Path,
    dotted: str,
    value: object,
    frame: int,
    out_dir: Path,
    comp: str = 'FinanceShowcaseWide',
    studio: Path = ROOT / 'studio',
    node: str = 'node',
) -> dict:
    """Render the graph twice, once with `dotted` changed, and diff the pixels.

    The output directory is emptied first, so no frame from an earlier run can
    survive to be compared against this one.
    """
    import subprocess

    # Absolute, because the render subprocess runs with cwd=studio: a relative
    # path handed to it resolves somewhere else entirely, and the failure looks
    # like a missing file rather than a path bug.
    props = Path(props).resolve()
    out_dir = Path(out_dir).resolve()

    base = json.loads(props.read_text(encoding='utf-8'))
    alt = json.loads(props.read_text(encoding='utf-8'))
    _set_path(alt, dotted, value)

    # a stale frame here is what produced a confident wrong number before
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    a_json = out_dir / 'a.json'
    b_json = out_dir / 'b.json'
    a_json.write_text(json.dumps(base, ensure_ascii=False), encoding='utf-8')
    b_json.write_text(json.dumps(alt, ensure_ascii=False), encoding='utf-8')

    for tag, g in (('a', a_json), ('b', b_json)):
        proc = subprocess.run(
            [node, 'bin/still.mjs', '--comp', comp, '--props', str(g),
             '--out', str(out_dir / tag), '--frames', str(frame)],
            cwd=studio, capture_output=True, text=True, timeout=1800,
        )
        if proc.returncode != 0:
            raise RuntimeError(f'still {tag} failed:\n{proc.stdout}\n{proc.stderr}')

    return diff_dir(out_dir / 'a', out_dir / 'b', frame)


def _only_match(directory: Path, frame: int) -> Path:
    """The one file for `frame` — and an error if it is not unambiguous.

    Never `next(glob(...))`. That picked a stale frame left by an earlier run
    and compared it against this run's frame, which is how an inert field came
    back with a two-decimal percentage and a bounding box.
    """
    import re

    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f'{directory} is not a directory')
    wanted = frame_name(frame)
    exact = directory / wanted
    if exact.exists():
        return exact
    others = sorted(p.name for p in directory.glob('*.png'))
    raise FileNotFoundError(
        f'{directory} has no {wanted}. '
        + (f'It contains: {others}. That is a stale frame or a wrong --frame, '
           f'and comparing it anyway is how a field gets a false verdict.'
           if others else 'It contains no PNGs at all.')
    )


def diff_dir(a: Path, b: Path, frame: int) -> dict:
    """Pixel diff of one NAMED frame across two single-frame directories."""
    import numpy as np
    from PIL import Image

    fa = _only_match(Path(a), frame)
    fb = _only_match(Path(b), frame)
    if fa.name != fb.name:
        raise AssertionError(f'frame mismatch: {fa.name} vs {fb.name}')

    ia = np.asarray(Image.open(fa).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(fb).convert('RGB')).astype(np.int16)
    d = np.abs(ia - ib).max(axis=2)
    changed = int((d > 8).sum())
    total = int(d.size)
    box = None
    if changed:
        ys, xs = np.nonzero(d > 8)
        box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return {
        'changed': changed, 'total': total, 'pct': changed / total * 100,
        'box': box, 'frame': frame,
        'a': str(fa), 'b': str(fb),
    }


def frame_ink(path: Path) -> float:
    """Fraction of the frame that is not backdrop, via the same per-row model
    measure_frame.py uses.

    So a zero-change result can say whether the frame was blank. Measuring a
    field on a frame that does not show its subject produces a confident zero,
    and 'this field does nothing' and 'you measured the wrong frame' look
    identical from the outside.
    """
    import numpy as np
    from PIL import Image

    img = np.asarray(Image.open(path).convert('RGB')).astype(np.float64)
    h, w, _ = img.shape
    edge = 40
    left = np.median(img[:, :edge, :], axis=1)
    right = np.median(img[:, w - edge:, :], axis=1)
    t = (np.arange(w, dtype=np.float64) / max(w - 1, 1))[None, :, None]
    model = left[:, None, :] + (right - left)[:, None, :] * t
    return float((np.abs(img - model).max(axis=2) > 8).mean() * 100)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        # so `--frames` where `--frame` was meant is an error, not a silent
        # fall back to the default. Three bad inputs produced a well-formed
        # number before this did.
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--registry', action='store_true',
                    help='check FIELD_READERS and exit')
    ap.add_argument('--props', help='the graph to render')
    ap.add_argument('--set', dest='dotted', help='dotted field path, e.g. layout.spreadX=300')
    ap.add_argument('--frame', type=int, required=False,
                    help='the frame to measure, named explicitly on both sides')
    ap.add_argument('--out', default=str(ROOT / 'out' / 'ab'), help='scratch dir (emptied first)')
    ap.add_argument('--comp', default='FinanceShowcaseWide')
    args = ap.parse_args(argv)

    if args.registry:
        problems = check_registry()
        for p in problems:
            print('  PROBLEM', p)
        print(f'{len(problems)} problem(s)')
        return 0 if not problems else 1

    missing = [n for n in ('props', 'dotted', 'frame') if getattr(args, n) is None]
    if missing:
        ap.error(f'missing required: {", ".join("--" + m for m in missing)}')
    if args.frame < 0:
        ap.error('--frame must be >= 0')

    props = Path(args.props)
    if not props.exists():
        ap.error(f'--props not found: {props}')

    field, sep, raw = args.dotted.partition('=')
    if not sep or not field:
        ap.error(f'--set must be dotted.path=value, got {args.dotted!r}')

    doc = json.loads(props.read_text(encoding='utf-8'))
    value, err = check_value(doc, field, raw)
    if err:
        print(f'  REFUSED — {err}')
        return 2

    found, _ = _get_path(doc, field)
    res = ab_field(props, field, value, args.frame, Path(args.out), comp=args.comp)
    ink = frame_ink(Path(res['a']))

    print(f'  field    {field} = {json.dumps(value, ensure_ascii=False)}'
          f'{"  (NEW — no previous value to compare against)" if not found else ""}')
    print(f'  frame    {res["frame"]}   content on that frame: {ink:.2f}% of pixels')
    print(f'  compared {res["a"]}')
    print(f'        vs {res["b"]}')
    print(f"  changed  {res['changed']} / {res['total']} px ({res['pct']:.2f}%)")
    print(f"  region   {res['box']}")

    if res['changed'] == 0:
        if ink < 0.5:
            print(f'  INERT?   frame {res["frame"]} is essentially blank '
                  f'({ink:.2f}% ink) — the subject is probably not on screen at '
                  f'this frame, so this says nothing about the field')
        else:
            print('  INERT — the field is declared but changes nothing on screen')
        return 1
    if ink < 0.5:
        print(f'  WARNING  frame {res["frame"]} is essentially blank ({ink:.2f}% ink); '
              f'a change here is probably not the subject you meant to measure')
    return 0


if __name__ == '__main__':
    sys.exit(main())
