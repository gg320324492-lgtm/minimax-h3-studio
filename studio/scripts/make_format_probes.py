"""Emit one probe graph per format, so P8 can be measured instead of asserted.

The P8 claim is that `format` in the graph owns the render: 8.1 says
calculateMetadata returns the graph's width/height/fps, 8.2 says a 1080p, a
vertical and a 4K render of the SAME graph come out right. Both are statements
about pixels, so both need a file to render.

Every probe here is the baseline graph with the three numbers inside `format`
substituted and NOTHING ELSE touched — same scenes, same durations, same
style_bible, same byte length in the surrounding text. That matters because
the cross-check in step 5 renders one frame twice and requires the content
bounding box to scale exactly; any edit beyond `format` would make a layout
difference indistinguishable from a layout bug.

`showcase_demo.json` is the cross-validation baseline and is opened
read-only. It is never a destination. If a probe has to differ in more than
`format` it does not belong here — write a separate graph.

`broken.json` is the exception on purpose, and it is the interesting one:
`format.width` is the STRING "1920", which showcase-v1's
`z.number().int().positive()` rejects. It is a well-formed probe precisely
because it is what a graph that gets written wrong looks like. The renderer's
response to it is the subject of step 2, not of this script.

Usage:
    python studio/scripts/make_format_probes.py
    python studio/scripts/make_format_probes.py --out out/p8_probes --verify-only

`--verify-only` re-checks probes already on disk against the baseline without
rewriting them, so the "only format changed" guarantee is testable later by
anyone and not only by the run that made the files. `--self-test` proves those
checks reject damage they are supposed to reject.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'pipeline' / 'examples' / 'showcase_demo.json'
DEFAULT_OUT = ROOT / 'out' / 'p8_probes'

#: name -> the three numbers to substitute. The baseline is 1920x1080@60, so
#: `hd` reproduces it and exists as the control every other probe is compared
#: against; `vertical` and `uhd` move one axis at a time so a measurement can
#: be attributed to a specific axis.
FORMATS: dict[str, tuple[object, object, object]] = {
    'hd': (1920, 1080, 60),
    'vertical': (1080, 1920, 60),
    'uhd': (3840, 2160, 60),
    'fps30': (1920, 1080, 30),
    # `width` as a string on purpose. showcase-v1 requires an integer, so this
    # document cannot parse and showcaseMeta has to decide what to do about it.
    'broken': ('1920', 1080, 60),
}

#: The format object, located in the source text rather than rebuilt from a
#: parsed dict, so substitution replaces three value tokens and preserves every
#: byte around them — indentation, key order, and the file's newline style.
_FORMAT_BLOCK = re.compile(
    r'(?P<key>"format"\s*:\s*\{)(?P<body>.*?)(?P<close>\})',
    re.DOTALL,
)


def _VALUE(name: str) -> re.Pattern[str]:
    """The `name: <value>` slot inside the format object.

    The value class excludes WHITESPACE, not just newline. Excluding only `\\n`
    looks sufficient and is not: on a CRLF file it matches `60\\r` for the last
    key, so the substitution silently deleted a carriage return and produced a
    3923-byte probe from a 3924-byte baseline. Content equality passed, JSON
    parsed, scenes matched — the file was only wrong at the byte level the
    script's own guarantee is written in.
    """
    return re.compile(rf'("{name}"\s*:\s*)([^,\s}}]+)')



def _substitute(text: str, width: object, height: object, fps: object) -> str:
    """Replace width/height/fps inside the top-level `format` object."""
    blocks = list(_FORMAT_BLOCK.finditer(text))
    if len(blocks) != 1:
        raise SystemExit(
            f'expected exactly one "format" object in {BASELINE}, found {len(blocks)}; '
            'this script only knows how to edit one, and guessing which was the '
            "document's format is how a probe would end up rendering the wrong one."
        )
    block = blocks[0]
    body = block.group('body')
    for name, value in (('width', width), ('height', height), ('fps', fps)):
        body, n = _VALUE(name).subn(
            lambda m: f'{m.group(1)}{json.dumps(value)}', body, count=1)
        if n != 1:
            raise SystemExit(f'no "{name}" key inside the format object of {BASELINE.name}')
    return text[: block.start()] + block.group('key') + body + block.group('close') + text[block.end():]


def _format_tokens(text: str) -> list[str]:
    """The three format values exactly as they appear in the source text."""
    block = list(_FORMAT_BLOCK.finditer(text))[0]
    out = []
    for name in ('width', 'height', 'fps'):
        m = _VALUE(name).search(block.group('body'))
        if not m:
            raise SystemExit(f'no "{name}" key inside the format object')
        out.append(m.group(2))
    return out


def _read_exact(path: Path) -> str:
    """Read a file WITHOUT newline translation.

    `Path.read_text()` runs universal newlines by default, so reading a CRLF
    file returns LF. Writing that back produced a probe whose only difference
    from the baseline was not `format`: all 191 line endings had flipped, which
    is 191 changed bytes in a file whose claim is that nothing outside `format`
    moved. Content-level equality did not catch it — the JSON parsed the same
    and the scenes matched — so the byte check below is the one that did.
    """
    return path.read_bytes().decode('utf-8')


def _byte_diff(a: str, b: str) -> list[int]:
    """Offsets at which two strings differ, for a short human-readable report."""
    return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


def outside_format(text: str, *names: str) -> str:
    """The document with the three format value tokens blanked out.

    Two documents that agree here agree everywhere the claim covers. Blanking
    the values rather than deleting the keys keeps the surrounding bytes — the
    quotes, the colon, the comma — under comparison too, so a probe that moved
    a comma is caught.
    """
    blocks = list(_FORMAT_BLOCK.finditer(text))
    if len(blocks) != 1:
        raise SystemExit(f'expected exactly one "format" object, found {len(blocks)}')
    block = blocks[0]
    body = block.group('body')
    for name in names:
        body, n = _VALUE(name).subn(lambda m: f'{m.group(1)}<VALUE>', body, count=1)
        if n != 1:
            raise SystemExit(f'no "{name}" key inside the format object')
    return text[: block.start()] + block.group('key') + body + block.group('close') + text[block.end():]


def _only_format_changed(baseline: dict, probe: dict) -> bool:
    """True when the two documents are equal everywhere except `format`."""
    a = {k: v for k, v in baseline.items() if k != 'format'}
    b = {k: v for k, v in probe.items() if k != 'format'}
    return a == b and 'format' in probe


def _self_test(baseline_text: str) -> int:
    """Prove the byte checks reject what they are supposed to reject.

    Both defects in this file's history were invisible to the JSON-level checks:
    191 flipped line endings parsed identically, and one lost carriage return
    inside `"fps": 60\\r` parsed identically too. A check that has never been
    shown to fail is not a check, so each damage is inflicted on the baseline
    here and the checks have to catch it.
    """
    import difflib

    cases: list[tuple[str, str]] = [
        ('CRLF flipped to LF', baseline_text.replace('\r\n', '\n')),
        # Exactly what the first version of _VALUE did to the last key in the
        # block: match `60\r` as the value, write `60`, and lose the carriage
        # return. The line count and the JSON are both unchanged.
        ('a carriage return eaten inside the fps value',
         baseline_text.replace('"fps": 60\r\n', '"fps": 60\n', 1)),
        ('a scene duration changed',
         baseline_text.replace('"durationInFrames": 229', '"durationInFrames": 230', 1)),
        ('a byte added to a scene id',
         baseline_text.replace('"s01_kpi"', '"s01_kpi "', 1)),
        ('the whole format object reformatted',
         baseline_text.replace('"width": 1920,', '"width":1920')),
    ]
    bad = 0
    for name, damaged in cases:
        outside = _byte_diff(outside_format(baseline_text, 'width', 'height', 'fps'),
                             outside_format(damaged, 'width', 'height', 'fps'))
        len_delta = len(damaged.encode('utf-8')) - len(baseline_text.encode('utf-8'))
        lines = sum(1 for d in difflib.unified_diff(
            baseline_text.splitlines(), damaged.splitlines(), n=0)
            if d.startswith(('+', '-')) and not d.startswith(('+++', '---')))
        caught = bool(outside) or len_delta != 0 or lines != 0
        print(f'  {"caught" if caught else "MISSED":7s} {name}: '
              f'{len(outside)} bytes outside format, length delta {len_delta:+d}, '
              f'{lines} differing lines')
        bad += not caught
    print(f'\n{"all damage detected" if not bad else f"{bad} case(s) slipped through"}')
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    ap.add_argument('--baseline', default=str(BASELINE),
                    help='the graph to derive probes from; it is opened read-only. '
                         'A second baseline is what lets the same machinery prove '
                         '"only format changed" for charts_demo.json instead of '
                         'growing a second copy of these checks that can drift.')
    ap.add_argument('--verify-only', action='store_true')
    ap.add_argument('--self-test', action='store_true',
                    help='check that the byte-level guard rejects damaged probes')
    args = ap.parse_args(argv)

    baseline_path = Path(args.baseline).resolve()
    out_dir = Path(args.out)
    baseline_text = _read_exact(baseline_path)
    baseline = json.loads(baseline_text)
    if 'format' not in baseline:
        raise SystemExit(f'{baseline_path} has no `format`; refusing to write probes from it')

    if args.self_test:
        return _self_test(baseline_text)

    if not args.verify_only:
        out_dir.mkdir(parents=True, exist_ok=True)

    try:
        shown_baseline = baseline_path.relative_to(ROOT)
    except ValueError:
        shown_baseline = baseline_path
    print(f'baseline  {shown_baseline}  {baseline["format"]}')
    print(f'probes    {out_dir}\n')

    failures = 0
    for name, (w, h, fps) in FORMATS.items():
        text = _substitute(baseline_text, w, h, fps)
        path = out_dir / f'{name}.json'
        if not args.verify_only:
            path.write_bytes(text.encode('utf-8'))

        written = _read_exact(path)
        try:
            probe = json.loads(written)
        except json.JSONDecodeError as exc:
            print(f'  {name:8s} INVALID JSON: {exc}')
            failures += 1
            continue

        checks: list[str] = []
        if not _only_format_changed(baseline, probe):
            checks.append('CHANGED MORE THAN format')
        if probe['format'] != {'width': w, 'height': h, 'fps': fps}:
            checks.append(f"format is {probe['format']}, wanted {{'width': {w!r}, "
                          f"'height': {h!r}, 'fps': {fps!r}}}")
        # Scene count and durations are the cross-check's basis: if a probe
        # disagreed with the baseline here, a bbox difference in step 5 could
        # be a different film rather than a different layout.
        if [s['durationInFrames'] for s in probe.get('scenes', [])] != \
           [s['durationInFrames'] for s in baseline['scenes']]:
            checks.append('scene durations differ from the baseline')
        # The byte-level guarantee, checked twice and for two different reasons.
        #
        # First: everything outside the three value tokens has to be identical,
        # which covers line endings, BOM and encoding. A CRLF baseline and an
        # LF probe are equal here once the values are blanked, so this check
        # alone would have passed a file with 191 changed bytes.
        diff = _byte_diff(outside_format(baseline_text, 'width', 'height', 'fps'),
                          outside_format(written, 'width', 'height', 'fps'))
        if diff:
            checks.append(f'{len(diff)} bytes differ outside the format values: '
                          f'first at offset {diff[0]}')
        # Second, and the one that catches value-token damage: the file's length
        # must equal the baseline's length plus exactly the change in the three
        # values. Blank-and-compare cannot see a lost character INSIDE a value,
        # which is precisely where the first version lost one.
        want_delta = sum(len(json.dumps(v)) - len(orig)
                         for v, orig in zip((w, h, fps), _format_tokens(baseline_text)))
        got_delta = len(written.encode('utf-8')) - len(baseline_text.encode('utf-8'))
        if got_delta != want_delta:
            checks.append(f'length delta is {got_delta:+d} bytes, the three values account '
                          f'for {want_delta:+d}')

        fmt = probe['format']
        note = '  (invalid on purpose: format.width is a string)' if name == 'broken' else ''
        status = 'FAIL' if checks else 'ok'
        # BYTES, not characters: the baseline's `_note` is Chinese, so a
        # character count reports a file smaller than it is and hides any
        # encoding damage. The guarantee this script makes is about bytes.
        print(f'  {name:8s} {status:4s} {fmt["width"]}x{fmt["height"]}@{fmt["fps"]}'
              f'  {len(written.encode("utf-8"))} bytes (baseline {len(baseline_text.encode("utf-8"))})'
              f'  {len(probe.get("scenes", []))} scenes{note}')
        for c in checks:
            print(f'           -> {c}')
            failures += 1

    print(f'\n{len(FORMATS) - failures}/{len(FORMATS)} probes '
          f'{"verified" if args.verify_only else "written"} to {out_dir}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
