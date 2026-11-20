"""p46_chart_probe.py — a chart-TYPE classifier, asked as a closed forced choice.

THE DEATH CAUSE THIS ATTACKS
----------------------------
P37 adjudicated 图表 (`docs/P37_REFERENCE_REANALYSIS.md:79`):

    | 7 | 图表 | B | 无测量 | 数「有几张图、什么类型」需要分类器，不是像素统计。
      目视见蜡烛图/散点/柱状/折线/期权链/统计卡，但目视不是测量 |

The stated cause is "needs a classifier". P45 built one classifier — a
string-presence reader — and the honest question is whether it transfers to
chart TYPE. It does not as-is: `vlm_critic.PROBE_QUESTION` asks whether a
given string is on a frame, which answers "is the number 48.2M printed", not
"what kind of chart is this". So this module asks its own question and reuses
P45's transport, its pinning and its UNAVAILABLE discipline unchanged.

WHY A FORCED CHOICE AND NOT PER-TYPE YES/NO
-------------------------------------------
The first design asked "does this image contain a bar chart?" per type. That
has a fatal ambiguity this project has already been bitten by twice
(`collision`, `rule_contrast_frame`): a `volume` chart in THIS renderer is
drawn by `VolumeBars`, whose own comment says it is "baseline-anchored, same as
Bar — see barBox". So "does it contain a bar chart" is genuinely true of a
volume frame, and the false-positive rate of the presence form would have been
measuring the QUESTION's ambiguity rather than the classifier.

A forced choice removes the ambiguity by construction: the model must name ONE
type, and the frame has one. It also makes the answer a single letter, so a
rambling or truncated answer is detectable instead of parsed hopefully — the
same reason `PROBE_QUESTION` asks for one word.

WHAT MAKES THE EXPECTED VALUE A MEASUREMENT RATHER THAN A TASTE
----------------------------------------------------------------
The correct letter is a function of the graph, not a judgement about the
picture: `p46_chart_control` renders one payload under five declared types and
proves each type changes the pixels. So "the frame at
`out/p46_probe/ours/type_bar/f00100.png` should answer B" is derived from the
input that caused the pixels, in the same sense P45's `expected_strings` is
derived from `formatValue` rather than from a human's opinion of the render.

THE VOCABULARY IS FOUR TYPES, NOT NINE, AND THAT IS MEASURED
-------------------------------------------------------------
`options.ts:CHART_TYPES` declares nine, and this question has four answers.

  * `area` WAS EXCLUDED HERE AND NO LONGER IS. It used to be excluded because
    `area` and `line` rendered byte-identical: `types.tsx`'s `LineOrArea`
    resolved the fill as `option('line','showArea',opts) ?? defaultArea` while
    `options.ts`'s `option()` never returns undefined, so `defaultArea` was
    unreachable. P47 moved the fill into a per-type default the resolver
    consults, and `area` now reaches the pixels as an area. Whether it is
    still inert is no longer written down anywhere in this directory — it is
    MEASURED, by `p46_chart_control.measured_inert_types()`, on every run,
    because the exclusion it replaced was a measurement frozen into a literal
    with a comment still claiming to be one. `area` is still not in the
    vocabulary below, and the reason is now the ordinary one: the letter set
    was fixed when this question was written and adding a letter changes the
    closed set the classifier is scored against. That is real work and is named
    as the open half of this dimension, not a finding.
  * `slope`, `heatmap`, `rank`, `bubble` — NOT ATTEMPTED HERE. They read
    `before`/`after`, `rows`, `items` and `series` respectively, so they cannot
    be swapped onto one payload without changing the data too; a pixel
    difference would then no longer isolate the type. Extending the vocabulary
    is real work and is named as the open half of this dimension.

NO OLLAMA REQUIRED: `ask()` takes the same `transport=` seam `vlm_critic` has,
and `tests/test_p46_probe_instruments.py` exercises every branch through it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from vlm_critic import DEFAULT_MODEL, ask_vlm, unavailable_reason

__all__ = [
    'OPTIONS', 'OPTION_LETTERS', 'NONE_LETTER', 'build_question',
    'parse_letter', 'unavailable', 'ask', 'ChartVerdict', 'census',
]

#: letter -> the mark it names. The descriptions are of the TYPE, not of any
#: frame: a criterion described in terms of one artefact is the criterion that
#: cannot be wrong about a correct one.
OPTIONS: dict[str, str] = {
    'A': 'a bar chart: solid filled rectangles standing side by side on one '
         'common baseline, each a different height',
    'B': 'a line chart: a single thin line drawn through a series of points, '
         'with no area filled in beneath it',
    'C': 'a volume chart: the same baseline-anchored rectangles as a bar '
         'chart but noticeably WIDER, with rounded top corners',
    'D': 'a sparkline: a small bare line drawing with no axis, no tick numbers '
         'and no frame around it',
}
NONE_LETTER = 'E'
OPTION_LETTERS = tuple(OPTIONS) + (NONE_LETTER,)

_LETTER = re.compile(r'\b([A-E])\b')


def build_question() -> str:
    """One closed question. The answer set is closed and every letter is used."""
    body = '\n'.join(f'{k}) {v}' for k, v in OPTIONS.items())
    return (
        f'This image shows a screen. Which of these describes it?\n{body}\n'
        f'{NONE_LETTER}) there is no data chart in this image at all\n'
        f'Answer with exactly one letter: A, B, C, D or {NONE_LETTER}.'
    )


def parse_letter(text: str) -> str | None:
    """The letter, or None when the model said something else.

    None is NOT a vote. An unreadable answer means the model did not do the
    task; scoring it as `E` would quietly inflate the no-chart column, and
    scoring it as a type would invent a measurement.
    """
    if not text:
        return None
    m = _LETTER.search(text.strip().upper())
    if not m:
        return None
    letter = m.group(1)
    return letter if letter in OPTION_LETTERS else None


def unavailable(path: Path, model: str = DEFAULT_MODEL,
                host: str | None = None,
                transport: Callable[..., dict] | None = None) -> str | None:
    """Why this frame cannot be judged, or None. Never returns a verdict.

    Delegates to `vlm_critic.unavailable_reason` rather than re-implementing it,
    so the rule "an absent judge is UNAVAILABLE and never a pass" has exactly
    one implementation in this repository.
    """
    kw: dict[str, Any] = {'model': model, 'transport': transport}
    if host is not None:
        kw['host'] = host
    return unavailable_reason(path, **kw)


def ask(path: Path, **kw: Any) -> tuple[str | None, str]:
    """`(letter, reason)`. letter is None whenever reason is not empty."""
    answer, why = ask_vlm(path, build_question(), **kw)
    if why:
        return None, why
    letter = parse_letter(answer or '')
    if letter is None:
        return None, (f'the model answered {answer!r}, which is not one of '
                      f'{list(OPTION_LETTERS)} — an unreadable answer is not a '
                      f'measurement')
    return letter, ''


@dataclass
class ChartVerdict:
    """One frame's census entry, and how it was reached."""

    path: str
    expected: str | None          # None = no ground truth (e.g. film frames)
    letter: str | None = None
    reason: str = ''
    raw: list[str] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)

    @property
    def correct(self) -> bool | None:
        """True/False when there is ground truth, None when there is not.

        `None` is the whole point of the `expected` field: an unscored frame
        must not be able to look like a right answer.
        """
        if self.expected is None or self.letter is None:
            return None
        return self.letter == self.expected


def census(items: list[tuple[Path, str | None]], times: int = 2,
           **kw: Any) -> list[ChartVerdict]:
    """Ask each frame `times` times; compare the answers byte for byte.

    `times=2` is the reproducibility column P45 established, kept because a
    classifier whose answer moves between runs cannot be quoted as a number.
    """
    import time

    out: list[ChartVerdict] = []
    for path, expected in items:
        v = ChartVerdict(path=str(path), expected=expected)
        for _ in range(max(1, times)):
            t0 = time.perf_counter()
            letter, why = ask(path, **kw)
            v.seconds.append(time.perf_counter() - t0)
            v.raw.append(letter if letter else f'<{why}>')
            if letter is not None and v.letter is None:
                v.letter = letter
            elif why:
                v.reason = v.reason or why
        # A disagreement between repeats is recorded, not averaged away.
        distinct = {r for r in v.raw if not r.startswith('<')}
        if len(distinct) > 1:
            v.reason = (v.reason + '; ' if v.reason else '') + (
                f'not reproducible across {len(v.raw)} asks: {sorted(distinct)}')
            v.letter = None
        out.append(v)
    return out


def score(verdicts: list[ChartVerdict]) -> dict[str, Any]:
    """Recall, false positives, reproducibility and the unscored pile — together.

    The four are reported as ONE dict on purpose. A recall printed without the
    number of frames that could not be scored is the shape P41 recorded at
    0/12, where the whole measurement was really about a chart whose values
    were never printed.
    """
    scored = [v for v in verdicts if v.expected is not None]
    unscored = [v for v in verdicts if v.expected is None]
    readable = [v for v in scored if v.letter is not None]
    correct = [v for v in readable if v.letter == v.expected]
    # A false positive is a chart frame answered `E`, or a no-chart frame
    # answered a chart letter. Both are "claimed something that is not there".
    fp = [v for v in readable if v.expected == NONE_LETTER and v.letter != NONE_LETTER]
    return {
        'asked': len(verdicts),
        'scored': len(scored),
        'unscored_no_ground_truth': len(unscored),
        'unreadable': len(scored) - len(readable),
        'correct': len(correct),
        'recall': f'{len(correct)}/{len(readable)}',
        'false_positives': f'{len(fp)}/{len([v for v in readable if v.expected == NONE_LETTER])}',
        'not_reproducible': [v.path for v in verdicts if 'not reproducible' in v.reason],
    }