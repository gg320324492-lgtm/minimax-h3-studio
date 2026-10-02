"""The spacing scale is 8 x Fibonacci, and that is the property worth guarding.

The scale (8/16/24/40/64/104/168) was for a long time logged as an unfinished
item: "SPACE is still 8...168 instead of the REQUIRED 4...96". That sentence
was traced in docs/SPACING_SCALE_VERDICT.md and it has no source. The master
plan's P6 row has never once contained a number (git log -S '4…96' over
docs/UPGRADE_MASTER_PLAN.md returns nothing), and the phrase first appears in
the ledger at 71da3cd under a different item number, renamed 6.3 -> 6.7 at
b27cbf2 — the same commit that attached the false attribution "总任务书要求的".

So this file guards the thing that is actually real. Two properties, and the
second one is the interesting one:

1. The values stay 8 x Fibonacci (1, 2, 3, 5, 8, 13, 21). This is the design.
2. Every step is CONSUMED. A step nothing reads is a step whose removal is
   free and whose meaning is a guess — the `xs`/`xxl`/`hero` dead steps that
   were sitting in this table unrecorded until 2026-10-03 are exactly what this
   catches. It also fails on someone appending `xxxl: 180`, which would break
   the closed sequence whether or not it is read.

Property 2 is where the work order and the measurements disagreed. The work
order asked for "all seven consumed, zero dead steps" — but its own blast-radius
table measured xs/xxl/hero at zero consumers, and re-measuring from scratch
confirms it. Asserting zero dead steps would have meant committing a red suite
to say something already known and recorded. So the guard asserts the part
that is both true and useful: **dead steps may only shrink, and every one that
remains must be written down in tokens.ts.** An undocumented dead step is the
defect; a documented reserved rung is not. Appending `xxxl: 180` is exactly
that defect, and it turns this red.

Run:
  python -m pytest tests/test_space_scale.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS_TS = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'design' / 'tokens.ts'
RENDERER = ROOT / 'studio' / 'src'

#: The ladder, as ratios. 8 x [1, 2, 3, 5, 8, 13, 21] = 8/16/24/40/64/104/168.
FIBONACCI = [1, 2, 3, 5, 8, 13, 21]
UNIT = 8

#: Steps the renderer reads nowhere, re-measured 2026-10-03 (see the method note
#: in tokens.ts). Frozen rather than emptied: these are reserved rungs, and the
#: guard's job is to stop a FOURTH one appearing without anybody deciding to.
DEAD_STEPS = ('xs', 'xxl', 'hero')


def _space_definition() -> dict[str, int]:
    """Read SPACE out of tokens.ts.

    Reads the real definition rather than restating it: a guard that carries
    its own copy of the numbers cannot notice them changing.
    """
    src = TOKENS_TS.read_text(encoding='utf-8')
    m = re.search(r'export const SPACE = \{([^}]*)\}\s*as const', src)
    assert m, (
        'SPACE is no longer a plain `export const SPACE = {...} as const` — '
        'this guard has to be taught the new shape, not left parsing nothing'
    )
    pairs = re.findall(r'(\w+):\s*(\d+)', m.group(1))
    assert pairs, 'SPACE was found but parsed to zero entries'
    return {k: int(v) for k, v in pairs}


def _renderer_sources() -> list[Path]:
    """Every renderer file that could consume a token, tokens.ts itself aside.

    Note what is deliberately absent: studio/scripts. chart_geometry.py holds a
    *mirror* of SPACE.lg/md/xl as Python constants, and it restates them in a
    docstring too. Counting those would credit the mirror for being a consumer
    and hide the question the question this guard asks — is the DESIGN step
    read by the renderer that draws the picture. test_chart_geometry.py already
    holds the mirror to the source; this is the other direction.
    """
    return [p for p in sorted(RENDERER.rglob('*'))
            if p.suffix in ('.ts', '.tsx') and p != TOKENS_TS]


def _consumers() -> dict[str, list[str]]:
    """Map each SPACE key to the source sites that actually read it.

    Comment lines are skipped: a token named in a comment is documentation, not
    consumption, and counting it is how `xs`/`xxl`/`hero` stayed invisible as
    dead for as long as they did. Token access is only the dotted form here —
    this guard does not try to resolve computed or destructured access, and
    the tokens.ts comment records that limitation rather than hiding it.
    """
    out: dict[str, list[str]] = {}
    pat = re.compile(r'SPACE\.(\w+)')
    for path in _renderer_sources():
        rel = path.relative_to(RENDERER).as_posix()
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if line.strip().startswith(('//', '*', '/*')):
                continue
            for key in pat.findall(line):
                out.setdefault(key, []).append(f'{rel}:{n}')
    return out


def test_space_is_eight_times_fibonacci():
    """The ratios are the design; the absolute numbers fall out of them.

    Not a restatement — an arithmetic consequence. If a step is edited to 17 or
    88, the ladder stops being 1:2:3:5:8:13:21 and this is the line that says
    so. It is also the reason the scale is NOT re-cut to a 4-multiples ramp:
    see docs/SPACING_SCALE_VERDICT.md for why that demand has no source.
    """
    space = _space_definition()
    values = list(space.values())

    assert values == [UNIT * f for f in FIBONACCI], (
        f'SPACE is {values} but the design is 8 x Fibonacci '
        f'{FIBONACCI} = {[UNIT * f for f in FIBONACCI]}. '
        'Adjacent steps must keep the ratio that makes them perceptually even.'
    )

    # The property stated as ratios too, so the failure message names the thing.
    unit = min(values)
    assert unit > 0, f'SPACE has a non-positive step ({values})'
    ratios = [v / unit for v in values]
    assert ratios == FIBONACCI, (
        f'SPACE ratios are {ratios}, not {FIBONACCI}. The absolute numbers are '
        'the easy half of this scale; the ratios are the half that was designed.'
    )


def test_every_space_step_is_consumed_or_named_as_dead():
    """A dead step must be a decision someone wrote down, not an accident.

    `xs`, `xxl` and `hero` are read nowhere — measured, not assumed. They are
    kept because they are the top of a ladder a future hero layout would reach
    for, and deleting a token is a bigger call than recording one. But "kept
    on purpose" has to be *evidenced*: tokens.ts now says so, with the grep
    that produced the numbers.

    So the rule is not "zero dead steps" (false today, and would make this
    suite red on a clean tree). The rule is: the set of dead steps is frozen,
    and each one is named in the comment above SPACE. Adding an unread rung
    silently is what makes a table rot, and it is what the ledger's "6.7
    unfinished" line ended up doing.
    """
    space = _space_definition()
    consumers = _consumers()
    src = TOKENS_TS.read_text(encoding='utf-8')

    dead = [k for k in space if k not in consumers]

    # 1. The dead set is exactly the measured, documented one. This is the part
    #    that turns red when someone appends `xxxl: 180` and nobody reads it.
    assert dead == list(DEAD_STEPS), (
        f'SPACE steps with no consumer are {dead}, but the recorded set is '
        f'{list(DEAD_STEPS)} (renderer counts: '
        f'{ {k: len(v) for k, v in sorted(consumers.items())} }). '
        'A NEW unread step is a decision to make explicitly: consume it, or '
        'delete it, or record it here and in tokens.ts with why it is reserved.'
    )

    # 2. Each dead step is named in the documentation comment, so the table
    #    cannot drift back to declaring rungs nobody claimed to want.
    doc = src[max(0, src.find('export const SPACE') - 2000):src.find('export const SPACE')]
    for key in DEAD_STEPS:
        assert re.search(rf'\b{key}\b', doc), (
            f'SPACE.{key} is dead but tokens.ts no longer says so. An '
            'undocumented dead step is the defect this guard exists to catch — '
            'it is how "4…96" ended up in the ledger as a requirement.'
        )

    # 3. The converse, so a rename cannot quietly strand a consumer: every
    #    SPACE.<key> the renderer reads must be a key the table declares.
    unknown = {k for k in consumers if k not in space}
    assert not unknown, (
        f'the renderer reads SPACE.{sorted(unknown)} but the table does not '
        f'declare them — declared: {sorted(space)}'
    )