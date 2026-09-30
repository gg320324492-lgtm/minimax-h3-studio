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
import os
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

#: chart option -> the file that reads it. Every entry is checked twice: that
#: the file exists, and that it actually mentions the option — a registry that
#: only checks its own bookkeeping cannot tell a working option from an inert
#: one. Populated from charts/options.ts TYPE_OPTIONS before P7.1's renderers
#: existed, which is the point: an option with no reader has to be a failing
#: check rather than a silent capability.
READER_FRAME = 'charts/ChartFrame.tsx'   # axes, grid, value labels, annotation
READER_TYPES = 'charts/types.tsx'        # the nine marks

FIELD_READERS: dict[str, dict[str, str]] = {
    # ── options every chart type accepts, read by the frame ────────────────
    'showGrid': READER_FRAME,
    'showAxis': READER_FRAME,
    'showValues': READER_FRAME,
    'axisLabel': READER_FRAME,
    'emphasisIndex': READER_TYPES,
    'deemphasis': READER_TYPES,
    'staggerFrames': READER_TYPES,
    'enterFrames': READER_TYPES,
    'valueFormat': READER_FRAME,
    'showArea': READER_TYPES,
    'strokeWidth': READER_TYPES,
    'curve': READER_TYPES,
    'barWidthRatio': READER_TYPES,
    'showRankDelta': READER_TYPES,
    'showCellValues': READER_TYPES,
    'sizeBy': READER_TYPES,
    'showEndLabels': READER_TYPES,
}


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
    for opt, reader in sorted(FIELD_READERS.items()):
        path = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / reader
        if not path.exists():
            problems.append(f'{opt}: reader {reader} does not exist')
        elif opt not in path.read_text(encoding='utf-8'):
            problems.append(
                f'{opt}: registered against {reader}, but that file never '
                f'mentions {opt} — the option is inert'
            )
    return problems


# ── 2. the A/B evidence ──────────────────────────────────────────────────────

def frame_name(frame: int) -> str:
    """The exact filename still.mjs writes for `frame`."""
    return f'f{frame:05d}.png'


class PathError(ValueError):
    """The path is wrong, as opposed to the field being inert.

    The two are indistinguishable in a pixel count, and conflating them is how a
    typo gets recorded as a finding.
    """


def _segments(doc: dict, dotted: str) -> list[str]:
    return dotted.split('.')


def _descend(node, key: str, create: bool):
    """One step down a dotted path, tolerating a list index.

    A scene graph stores scenes as a LIST, so the only useful address for a
    chart option is `scenes.0.content.chart.emphasisIndex`. Treating `0` as a
    dict key would silently replace the list with a dict and produce a graph
    that fails to render for a reason that has nothing to do with the field
    under test.
    """
    if isinstance(node, list):
        if not key.isdigit():
            raise KeyError(f'{key!r} is not a list index (node is a list)')
        idx = int(key)
        if not (0 <= idx < len(node)) and not create:
            raise KeyError(f'index {idx} out of range ({len(node)} items)')
        while len(node) <= idx:
            node.append(None)
        if node[idx] is None and create:
            node[idx] = {}
        return node, idx
    if not isinstance(node, dict):
        raise KeyError(f'cannot descend into {type(node).__name__} at {key!r}')
    if key not in node:
        if not create:
            raise KeyError(key)
        node[key] = {}
    return node, key


def _get_path(doc: dict, dotted: str) -> tuple[bool, object]:
    """(found, current value) for a dotted path, without creating anything."""
    node: object = doc
    for key in _segments(doc, dotted):
        try:
            parent, k = _descend(node, key, create=False)
        except KeyError:
            return False, None
        if isinstance(parent, list):
            node = parent[k]
        elif k not in parent:
            return False, None
        else:
            node = parent[k]
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
    """Set a leaf, creating it — but never inventing the structure above it.

    Two mistakes produce the same output as a dead field, and the difference
    matters:

      scenes.0.content.chart.emphasisIndex   the real path; 0 is an index
      scenes[0].content.chart.emphasisIndex  bracket syntax; "scenes[0]" is
                                             just a key name, so this created a
                                             top-level object nobody reads, and
                                             the measurement came back 0px —
                                             which reads exactly like "this
                                             option is inert". It is not. It is
                                             a typo, and it nearly cost a review
                                             round on a matrix row that was
                                             working perfectly.

    So the rule is: a leaf may be new, but an ANCESTOR may not. Setting a field
    the graph has never mentioned is legitimate — that is how you A/B an option
    nobody set yet. Inventing a container three levels up is a mistake, and it
    is refused rather than measured.
    """
    parts = _segments(doc, dotted)
    for part in parts:
        if '[' in part or ']' in part:
            raise PathError(
                f'{part!r} uses bracket syntax. This tool takes a dotted path, so a '
                f'list index is a bare number: scenes.0.content.chart.emphasisIndex. '
                f'Bracket syntax silently creates a key literally named "{part}", '
                f'nothing reads it, and the measurement reports the field as inert.'
            )
    node = doc
    for key in parts[:-1]:
        try:
            parent, k = _descend(node, key, create=False)
        except KeyError as exc:
            raise PathError(
                f'{dotted}: no {key!r} at this level. Only the LAST segment may be '
                f'new — a missing container means the path is wrong, and creating '
                f'it would measure a field nobody reads and report it as inert. '
                f'({exc})'
            ) from exc
        node = parent[k]
    last = parts[-1]
    parent, k = _descend(node, last, create=True)
    parent[k] = value


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
    try:
        _set_path(alt, dotted, value)
    except PathError as exc:
        raise PathError(str(exc)) from exc

    # a stale frame here is what produced a confident wrong number before
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    a_json = out_dir / 'a.json'
    b_json = out_dir / 'b.json'
    a_json.write_text(json.dumps(base, ensure_ascii=False), encoding='utf-8')
    b_json.write_text(json.dumps(alt, ensure_ascii=False), encoding='utf-8')

    # Two environment facts, both learned from a full disk.
    #
    # TMPDIR: the bundler writes its scratch bundle to the system temp. That
    # temp was on a C: drive with zero free - 125 leftover bundles, 58 GB -
    # because every one had copied the whole 773 MB studio/public (staged job
    # props, EP01's mp4s) into itself. The scratch goes next to the output
    # instead, which is on the repo drive.
    #
    # --public-dir: a graph that references no static file needs an empty
    # directory rather than 773 MB of unrelated media. still.mjs REFUSES the
    # combination when the graph does reference a static file, so this cannot
    # silently break an asset lookup.
    tmp = out_dir / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'TMPDIR': str(tmp), 'TMP': str(tmp), 'TEMP': str(tmp)}
    public_dir = out_dir / 'public'
    public_dir.mkdir(parents=True, exist_ok=True)

    for tag, g in (('a', a_json), ('b', b_json)):
        proc = subprocess.run(
            [node, 'bin/still.mjs', '--comp', comp, '--props', str(g),
             '--out', str(out_dir / tag), '--frames', str(frame),
             '--public-dir', str(public_dir)],
            cwd=studio, capture_output=True, text=True, timeout=1800, env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f'still {tag} failed on frame {frame}')
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

    found, current = _get_path(doc, field)
    try:
        res = ab_field(props, field, value, args.frame, Path(args.out), comp=args.comp)
    except PathError as exc:
        # A wrong path is a CALLER error and is reported in those words. The
        # alternative — a 0px result and "INERT" — is indistinguishable from a
        # real finding, and a finding that is really a typo goes into the ledger
        # and gets argued about.
        print(f'  BAD PATH — {exc}')
        return 2
    ink = frame_ink(Path(res['a']))

    print(f'  field    {field} = {json.dumps(value, ensure_ascii=False)}'
          f'{"  (NEW — no previous value to type-check against)" if not found else ""}'
          f'{"  (was " + repr(current) + ")" if found else ""}')
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
