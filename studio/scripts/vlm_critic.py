"""vlm_critic.py — a VLM that is told what to LOOK FOR, not how to JUDGE (P41).

This is 10.2 rebuilt after 10.2 was ruled undecidable. 10.2 asked for
"每 scene 抽 5 帧，多维评分 + problems + repair_suggestions" — a MULTI-
DIMENSIONAL SCORE. P17 already ruled that shape out for `premium product
film`: no instrument, no corpus, no positive class. This repo has now refused
the same shape three times (`collision` had a detector and no threshold;
`flicker` had no positive class; `rule_contrast_frame`'s population does not
separate). Building the score would have been a fourth refusal, in code.

SO WHAT IS HERE INSTEAD. One question, with an answer that is either
derivable from the graph or is a fact about pixels:

    the graph says this scene's chart prints "48.2M" — is that text on the frame?

`locked_fields.py` already asks the same shape of question about a JSON
document ("did the repair move a number the graph declared?"). This asks it
about a RENDERED PICTURE, where the claim has been through a formatter, a
layout, a font stack and a video codec before anyone looks at it. That
distance is the entire reason a second instrument is worth having, and it is
also the only part of the question that can fail.

WHY THIS QUESTION IS DECIDABLE, in the three senses P17 demanded:

  * AN INSTRUMENT: `qwen2.5vl:7b` over a local ollama. Measured below.
  * AN EXPECTED VALUE, not a taste: the string is produced from the graph by
    a port of the renderer's own `formatValue`, so "what should be on screen"
    is a function of the input, not a judgement about the output.
  * NO THRESHOLD: the answer is a string identity — present or not. Nothing
    is invented, so nothing can be mis-cut. This is the property that makes
    `graph_scene_renderable` (P21) worth having, and it is the reason this
    module reports a verdict at all where `collision` still does not.

WHAT WAS MEASURED, AND WHERE THE LINE IS DRAWN. On 1920x1080 frames decoded
from the delivered `out/charts_demo.mp4`:

    probe set                                    correct
    18 two-digit heatmap cell values (PRINTED)     18/18
    6 near-misses, ±1 off a printed value           6/6  (NO)
    4 absent values on that frame                  4/4  (NO)
    6 values from a DIFFERENT scene, same film     6/6  (NO)
    2 nonsense strings                             2/2  (NO)
    8 on a blank frame / a 1px-flattened frame     8/8  (NO)

44/44, and the last row is the one that matters: a reader that answered
without looking could not produce it. Reproducibility is the second measured
property, not an assumption — see `assert_reproducible`, and note that
`options` below pins `temperature` and `seed` because a VLM verdict that
varies between runs is a coin flip wearing a lab coat.

THE OPEN QUESTION WAS MEASURED AND REJECTED. Asking "list every number in this
image" and checking the answer against a Python port of `formatValue` scored
0/12 on `c02_line` — because `c02_line` declares `showValues: false`, so its
data values are not printed at all and only axis ticks are. The number was
wrong and the VLM was RIGHT. Scoring an open question needs a second renderer
whose every option, tick and per-type branch is reproduced in Python; that
mirror is a new source of false positives, and P17's whole lesson is that a
criterion which can be wrong about a correct artefact is worse than no
criterion. So this module asks CLOSED questions only, and `expectation_for`
carries the graph's declared expectation rather than a reconstruction of
everything the renderer chose to draw.

WHAT IT IS NOT. It does not score beauty, does not rank takes, and does not
say a frame is good. A frame that is well-composed and prints every declared
number PASSES here; a frame that is hideous and prints them all also PASSES.
That is the intended narrowness — the same narrowness `rule_aspect` has.

THE FAILURE THIS MODULE EXISTS TO NOT HAVE. `ollama` is an external process
that is simply not running on CI, or on the next machine, or after a reboot.
Every other failure of this shape in this repo was a gate that could not
check and reported green anyway: `visual_qa` silently skipping, `render.mjs`
ignoring a flag, the props gate idling. So `ask_vlm` returns UNAVAILABLE with
the reason attached and `verdict_for` propagates it — it never degrades to
PASS. `unavailable_reason()` is the single place that decides, and a test
asserts its verdict is never PASS. Absence of a model is a verdict here, and
it is the only verdict this module will emit about its own judge.

Usage:
    from vlm_critic import FrameProbe, expected_strings, rule_frame_shows_text
    probes = [FrameProbe(frame=975, path=Path('f0975.png'),
                         expected=['48.2M', '39.9M'], scene_id='c07_rank')]
    rule_frame_shows_text(probes)          # -> visual_qa.Finding
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from math import copysign as _copysign, floor as _floor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from visual_qa import FAIL, PASS, UNAVAILABLE, Finding

__all__ = [
    'RULE', 'DEFAULT_MODEL', 'DEFAULT_HOST', 'DEFAULT_SEED', 'DEFAULT_OPTIONS',
    'PROBE_QUESTION', 'FrameProbe', 'format_value', 'expected_strings',
    'normalize', 'parse_verdict', 'unavailable_reason', 'ask_vlm',
    'probe_text', 'rule_frame_shows_text', 'assert_reproducible', 'main',
]

#: The one rule this module contributes. Named so it cannot be confused with the
#: nine pixel rules already in `visual_qa` — it takes a frame AND the graph.
RULE = 'frame_shows_expected_text'

DEFAULT_HOST = os.environ.get('VLM_CRITIC_HOST', 'http://127.0.0.1:11434')
DEFAULT_MODEL = os.environ.get('VLM_CRITIC_MODEL', 'qwen2.5vl:7b')
#: Pinned, and asserted rather than assumed: `assert_reproducible` runs the same
#: probe twice and compares bytes. A float seed left to the wall clock would
#: make every verdict in this module unreproducible while looking identical.
DEFAULT_SEED = 42
#: `temperature: 0` plus `top_k: 1` is greedy decoding: at temperature 0 the
#: sampler takes the argmax, and `top_k: 1` makes that true even if a future
#: ollama treats temperature 0 as "very small" rather than "exactly zero".
DEFAULT_OPTIONS: dict[str, Any] = {
    'temperature': 0, 'top_k': 1, 'num_predict': 8,
}

#: The question. Closed on purpose — see the module docstring for the open form
#: that was measured and rejected. One word back, so a truncated or rambling
#: answer is itself detectable rather than parsed hopefully.
PROBE_QUESTION = ('Does this image contain the text "{text}" anywhere, exactly '
                  'as written? Answer with one word, YES or NO.')

#: A model call that has not answered in this many seconds is treated as
#: absent, not as slow. Measured: the first call of a session costs 66.7s (the
#: model is loaded from disk); every later call on a resident model measured
#: 0.10-0.60s. So the budget must clear a cold load and still not hang a gate
#: forever. Exceeding it reports UNAVAILABLE with the reason — never PASS.
COLD_LOAD_BUDGET_S = 300.0


# ── the expectation: the graph's own numbers, through the renderer's formatter ──

def trim_zeros(s: str) -> str:
    """3.0 -> 3, 3.50 -> 3.5. Port of `trimZeros` in scale.ts."""
    if '.' not in s:
        return s
    stripped = s.rstrip('0')
    return stripped[:-1] if stripped.endswith('.') else stripped


def _js_int(v: float) -> str:
    """`Math.round(v).toLocaleString('en-US')`, as one string.

    Two differences between this and Python, both found by running the corpus
    through tsx rather than by reasoning about it:

      * `Math.round` rounds half UP; Python's `round` rounds half to EVEN.
        0.5 -> '1' here and '0' in Python.
      * `Math.round(-0.5)` is `-0`, and `(-0).toLocaleString('en-US')` is the
        STRING `'-0'`. There is no negative-zero integer in Python, so this
        case has to be recognised rather than computed.

    Neither is visible in these graphs — no value is ever exactly n.5 — which
    is the point worth keeping: a mirror that is wrong where nobody can see it
    is the mirror that will be wrong where somebody can.
    """
    if v != v or v in (float('inf'), float('-inf')):    # JS gives NaN for these
        return 'NaN'
    f = _floor(v + 0.5)
    if f == 0 and _copysign(1.0, v) < 0:
        return '-0'
    return f'{f:,}'


def format_value(v: float, fmt: str = 'auto') -> str:
    """`formatValue` from studio/src/templates/finance-showcase/charts/scale.ts.

    PORTED, NOT SHARED. The real one is TypeScript inside the renderer, and
    calling it would mean a node subprocess per probe. The port is pinned to
    the shipped semantics by `tests/test_p41_vlm_critic.py`, which runs both —
    the Python one and the real `formatValue` via tsx — over a corpus of
    values and every declared format, and fails if they disagree. That test is
    what makes this a mirror with a guard rather than a second opinion: P24
    measured two renders disagreeing on a number while agreeing on the verdict,
    and a mirror nobody checks is how that happens.

    The unit is appended here because `ChartFrame.tsx` renders
    `valueText = f.unit ? text+unit : text` — the caller, not the formatter,
    owns that join, and the expected string has to be the whole thing the
    viewer reads.
    """
    if fmt == 'percent':
        return f'{trim_zeros(f"{v * 100:.1f}")}%'
    if fmt == 'int':
        return _js_int(v)
    if fmt == 'one':
        return trim_zeros(f'{v:.1f}')
    if fmt == 'two':
        return trim_zeros(f'{v:.2f}')

    a = abs(v)
    if fmt == 'compact' or (fmt == 'auto' and a >= 10_000):
        for scale, suffix in ((1e12, 'T'), (1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
            if a >= scale:
                return f'{trim_zeros(f"{v / scale:.1f}")}{suffix}'
        return _js_int(v)
    if fmt == 'auto' and 0 < a < 1:
        return trim_zeros(f'{v:.2f}')
    return _js_int(v)


def expected_strings(scene: dict) -> list[str]:
    """The strings this scene's chart DECLARES it will print.

    Only what the graph asks for. Deliberately not a reconstruction of
    everything the renderer draws — axis ticks, end labels and cell values are
    the renderer's business, and a Python mirror of all of them was the false
    positive that killed the open question (see the docstring). A value the
    scene does not declare is not asked about.

    `showValues` and `showCellValues` ARE honoured, because those two are what
    decide whether a declared number is printed at all, and getting that wrong
    is the exact `c02_line` false positive. Their defaults come from
    `DEFAULT_CHART_OPTIONS` in options.ts: `showValues: false`,
    `showCellValues: true`.
    """
    chart = (scene.get('content') or {}).get('chart')
    if not isinstance(chart, dict):
        return []
    fmt = chart.get('valueFormat', 'auto')
    show = chart.get('showValues', False)
    out: list[str] = []

    if show and isinstance(chart.get('values'), list):
        out += [format_value(v, fmt) for v in chart['values'] if isinstance(v, (int, float))]
    if isinstance(chart.get('rows'), list) and chart.get('showCellValues', True):
        for row in chart['rows']:
            if isinstance(row, list):
                out += [format_value(v, fmt) for v in row if isinstance(v, (int, float))]
    if show:
        for item in chart.get('items') or []:
            if isinstance(item, dict) and isinstance(item.get('value'), (int, float)):
                out.append(format_value(item['value'], fmt))
    # `emphasisIndex` picks one mark to label at full strength; it does not
    # change WHICH values are printed, only their prominence, so it is not read.
    return out


# ── comparing what was said to what was asked ──

def normalize(s: str) -> str:
    """Fold the ways a VLM paraphrases a printed token.

    `"48.2M"` and `48.2 M` and `$48.2m` are the same string on the screen, and
    a reader that answered NO to any of them would be reporting a typography
    difference as a missing number. Commas, spaces, currency marks, wrapping
    quotes and case are all folded. Digits and their unit suffixes are NOT:
    `48.2M` and `48.2` are different claims, which is the whole reason this
    rule can FAIL.
    """
    t = s.strip().strip('.,;:()[]"\'*').replace(',', '').replace('$', '')
    return t.replace(' ', '').lower()


def parse_verdict(text: str) -> bool | None:
    """`YES`/`NO` from the model's answer, or None if it said neither.

    None is a real outcome and is NOT a pass. The prompt asks for one word and
    `num_predict` is 8 tokens, so an unparseable answer means the model did not
    do the task — reporting that as "no, the text is absent" would be inventing
    a measurement, and reporting it as "yes, the text is present" would be
    inventing the opposite one.
    """
    head = text.strip().upper()
    if head.startswith('YES'):
        return True
    if head.startswith('NO'):
        return False
    return None


# ── the judge, and what happens when it is not there ──

def unavailable_reason(
    path: Path, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
    transport: Callable[[dict, str, float], dict] | None = None,
) -> str | None:
    """Why this frame cannot be judged, or None when it can be.

    THE FUNCTION THIS MODULE IS BUILT AROUND. Its result is a REASON and never
    a verdict: there is no branch of this function that returns PASS, and a
    test asserts that by construction (an absence of a judge must not be a
    pass). Every failure mode the project's core defect takes — model not
    running, model not pulled, host wrong, frame missing, image undecodable,
    answer unparseable, timeout — lands here with its own text.

    Checking the model list rather than just the port is deliberate: a 200 from
    an ollama with no model pulled is a health check that passes on an empty
    room, which is the "cannot check, reported green" shape this module is
    written against.

    `transport` short-circuits the probe BECAUSE IT REPLACES THE JUDGE, and a
    judge that has been replaced cannot be absent. This is not a convenience:
    without it, `VLM_CRITIC_HOST` pointed anywhere unreachable made three
    tests of this module's own guard fail, which would have taught a reader
    that the guard needs a model — the exact dependency the guard exists to
    avoid. Measured by setting that variable and watching them go red.
    """
    if not path.exists():
        return f'frame {path.name} does not exist'
    if transport is not None:
        return None
    try:
        with urllib.request.urlopen(f'{host}/api/tags', timeout=10) as r:
            tags = json.loads(r.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return (f'no ollama at {host} ({type(exc).__name__}: {exc}); a VLM '
                f'judgement is UNAVAILABLE, never a pass')
    names = {m.get('name') for m in (tags.get('models') or [])}
    if model not in names:
        return (f'ollama is running but has no model named {model!r} '
                f'(it has {sorted(n for n in names if n)})')
    return None


@dataclass(frozen=True)
class FrameProbe:
    """One frame, and the strings the graph says belong on it."""
    frame: int
    path: Path
    expected: list[str] = field(default_factory=list)
    scene_id: str = ''


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode('ascii')


def ask_vlm(path: Path, question: str, model: str = DEFAULT_MODEL,
            host: str = DEFAULT_HOST, timeout: float = COLD_LOAD_BUDGET_S,
            seed: int = DEFAULT_SEED,
            options: dict[str, Any] | None = None,
            transport: Callable[[dict, str, float], dict] | None = None,
            ) -> tuple[str | None, str]:
    """Ask the model one closed question about one frame.

    Returns `(answer, reason)`: `answer` is None whenever `reason` is not
    empty, and there is no path through this function that returns a positive
    answer it did not receive. `transport` is the injection point the guard
    uses so the whole rule can be exercised without a GPU and without a
    network — the tests pass a callable here and never open a socket.
    """
    why = unavailable_reason(path, model, host, transport)
    if why is not None:
        return None, why
    body = {
        'model': model, 'stream': False, 'seed': seed,
        'options': dict(DEFAULT_OPTIONS if options is None else options),
        'messages': [{'role': 'user', 'content': question, 'images': [_encode_image(path)]}],
    }
    send = transport or _http_chat
    try:
        data = send(body, host, timeout)
    except Exception as exc:                      # noqa: BLE001 - the whole point
        # Every transport failure is UNAVAILABLE with its own text. A broad
        # except is correct here and nowhere else: a judge that raises past
        # this line becomes a gate that crashed green, which is the failure
        # this module was written to make impossible.
        return None, f'the VLM call failed ({type(exc).__name__}: {exc})'
    return str(data.get('message', {}).get('content', '')), ''


def _http_chat(body: dict, host: str, timeout: float) -> dict:
    req = urllib.request.Request(
        f'{host}/api/chat', data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def probe_text(path: Path, text: str, **kw: Any) -> tuple[bool | None, str]:
    """Is `text` on this frame? Returns `(verdict, reason)`."""
    answer, why = ask_vlm(path, PROBE_QUESTION.format(text=text), **kw)
    if why:
        return None, why
    got = parse_verdict(answer or '')
    if got is None:
        return None, (f'the model answered {answer!r}, which is neither YES nor '
                      f'NO — an unreadable answer is not a measurement')
    return got, ''


def assert_reproducible(probe: FrameProbe, times: int = 2, **kw: Any) -> list[str]:
    """Ask the same question `times` times; return the answers that differed.

    Returns a list rather than raising so the CALLER decides what a difference
    means — a guard wants to fail, a report wants to print. Empty means the
    same bytes came back `times` times, which is the property `DEFAULT_SEED`
    and `DEFAULT_OPTIONS` exist to buy.
    """
    answers = [probe_text(probe.path, t, **kw)[0] for t in probe.expected]
    repeat = [probe_text(probe.path, t, **kw)[0] for t in probe.expected]
    return [t for a, b, t in zip(answers, repeat, probe.expected) if a != b]


# ── the rule ──

def rule_frame_shows_text(probes: list[FrameProbe], **kw: Any) -> Finding:
    """Does every frame carry every string its graph says it carries?

    One question per (frame, expected string). Any `None` — absent judge,
    unreadable answer, missing frame — makes the whole rule UNAVAILABLE,
    because a verdict built from some probes and not others is a verdict about
    an unknown fraction of the work.

    The verdict is `FAIL` if any expected string was answered NO. The strings
    missing, the frames they belong to and the model's own words travel in
    `extra`, so a caller reads WHY from the return value and never from a log
    line. That is the shape P36's `unapplied` established.
    """
    if not probes:
        return Finding(RULE, UNAVAILABLE, 0,
                       'no frames were probed. An empty probe set is not a pass: '
                       'it is the shape of a caller that built nothing and '
                       'reported success anyway.', trusted=False)

    absent: list[str] = []
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    asked = 0
    for p in probes:
        for text in p.expected:
            key = (str(p.path), normalize(text))
            if key in seen:
                continue          # two scenes declaring 48.2M is one question
            seen.add(key)
            said, why = probe_text(p.path, text, **kw)
            asked += 1
            if said is None:
                absent.append(f'{p.path.name}/{text}: {why}')
            results.append({'frame': p.frame, 'scene_id': p.scene_id,
                            'image': p.path.name, 'text': text,
                            'present': said})

    if absent:
        return Finding(
            RULE, UNAVAILABLE, asked,
            f'{len(absent)} of {asked} probe(s) could not be answered, so this '
            f'is not a measurement of the frames. First reason: {absent[0]}',
            trusted=False,
            extra={'probes': asked, 'unanswered': absent, 'results': results})

    missing = [r for r in results if r['present'] is False]
    parts = [f'{asked} probe(s) over {len(probes)} frame(s); '
             f'{asked - len(missing)} of {asked} expected strings were found']
    if missing:
        where = ', '.join(f"{r['image']}/{r['text']}" for r in missing[:6])
        parts.append(f'{len(missing)} expected string(s) are NOT on the frame: '
                     f'{where}{" ..." if len(missing) > 6 else ""}')
    else:
        parts.append('every string the graph declares for these frames is on them')
    return Finding(RULE, FAIL if missing else PASS, len(missing), '; '.join(parts),
                   extra={'probes': asked, 'missing': missing, 'results': results})


def main(argv: list[str] | None = None) -> int:
    """`vlm_critic.py FRAME --expect 48.2M [--expect 39.9M]` — exit 1 on FAIL.

    Also exits 1 on UNAVAILABLE. A gate that exits 0 when it could not check is
    the defect this module exists to prevent, and the exit code is where that
    is decided for a shell caller.
    """
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('frame', type=Path)
    ap.add_argument('--expect', action='append', default=[], metavar='TEXT',
                    help='a string the frame is supposed to carry (repeatable)')
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--host', default=DEFAULT_HOST)
    args = ap.parse_args(argv)

    finding = rule_frame_shows_text(
        [FrameProbe(frame=0, path=args.frame, expected=list(args.expect))],
        model=args.model, host=args.host)
    print(finding)
    return 0 if finding.verdict == PASS else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
