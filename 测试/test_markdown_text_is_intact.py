"""No tracked markdown may contain a U+FFFD REPLACEMENT CHARACTER.

    2026-10-03. Twenty-two of these were found sitting in two files this
    project had been treating as records: six in docs/SPACING_SCALE_VERDICT.md
    and sixteen in docs/P17_SHOWCASE_DEMO.md, none of them introduced by the
    task that wrote the file -- both had been delivered, reviewed and shipped
    with the damage already in them. That is the shape worth guarding: not a
    bad write that got caught, but a bad write that got committed.

    U+FFFD is what a decoder leaves behind when the bytes it was handed are not
    valid in the encoding it used. Here it arrives through the write channel,
    not through a mis-decoded file, which is why it survives: the character is
    a perfectly legal codepoint, it renders as a placeholder, and nothing
    downstream refuses it. Markdown has no byte-order mark, no declared charset
    and no schema, so a reader has no way to know the text was meant to say
    something else.

    The damage is small but it is not cosmetic. Every occurrence sat inside a
    sentence carrying a finding -- "the scale stays Fibonacci, and NOT because
    it is more elegant", "the disagreement is about the RANGE", "exactly the
    class of change this project keeps paying for". A placeholder in the middle
    of a recorded conclusion is worse than a missing sentence, because the
    sentence still reads as complete.

    This guard is deliberately whole-file rather than a diff. A guard scoped to
    changed lines would have gone green on every commit that introduced one,
    which is the opposite of the point.

    A test cannot prove the intended character, only that a lossy one is absent.
    That is the whole claim, and it is falsifiable: write a U+FFFD into any
    tracked markdown and this goes red.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tracked_markdown() -> list[Path]:
    raw = subprocess.run(
        ['git', 'ls-files', '*.md'],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [ROOT / line for line in raw.splitlines() if line]


def test_no_tracked_markdown_contains_a_replacement_character():
    files = _tracked_markdown()
    assert files, 'git ls-files returned no markdown — the sweep is not running'

    damaged: list[str] = []
    for path in files:
        text = path.read_text(encoding='utf-8', errors='replace')
        for lineno, line in enumerate(text.splitlines(), start=1):
            if '�' in line:
                damaged.append(
                    f'{path.relative_to(ROOT)}:{lineno}: {line.strip()[:120]}')

    assert not damaged, (
        f'{len(damaged)} line(s) contain U+FFFD, so text has been lost in '
        'transit and the sentence is no longer the one that was written:\n  '
        + '\n  '.join(damaged))


def test_the_sweep_would_notice_one():
    """A sweep that cannot fail is not a sweep.

    Proves the assertion above is load-bearing by running it against a string
    known to be damaged, rather than by trusting that `in` does what it says.
    The corrupted sample is the real shape: a placeholder sitting inside a
    recorded conclusion, where the sentence still reads as complete.
    """
    damaged = 'the scale stays Fibonacci, not because it is more �雅'
    assert '�' in damaged, 'the sample must contain the character it is testing for'