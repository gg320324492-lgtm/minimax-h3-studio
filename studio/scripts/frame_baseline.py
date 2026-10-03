"""frame_baseline.py — a per-job baseline, and what it is allowed to compare.

P24. The work order's question was the blocking one: P13 measured three reruns of
ONE render differing in bytes (demo1/demo2/demo3.mp4 = 711054 / 710851 / 712303),
so "if every render differs, what is a baseline comparing?" This file answers it
by measurement and is deliberately narrow — it is a COMPARISON, not a gate and
not a new rule.

WHAT THE MEASUREMENT SAID, AND WHY THE COMPARISON OBJECT IS THE VERDICT
----------------------------------------------------------------------
Both were measured on the six real rerun pairs already in `out/p13_probe` —
(full_a,full_b), (full_a,full_r2), (full_b,full_r2), (fr_a,fr_b), (xc1a,xc1b)
and (s1,s2) — which are two runs of ONE render, 226 frames of comparison per
rule:

    rule           measured  value differs  verdict differs  max rel spread
    black_frame          226             86                0        0.4250%
    blur                 226             91                0       16.1488%
    clipping             226             18                0        1.6667%
    contrast_frame       226              0                0              -
    font_size            226             37                0       96.8750%
    safe_area            226              9                0        3.2967%

    VERDICT reproducibility: 1356/1356 identical (100.00%)

So the bytes are not reproducible and the numbers are not either — `font_size`
reads 96.9% apart between two runs of the same render — while the VERDICT was
identical in every one of 1356 comparisons. A baseline over the numbers would
be noise: it would fire on reruns of an unchanged render, which is precisely
the "red for a constant" defect P22 removed. A baseline over the verdicts is
the one thing measured to be stable, so THAT is what this compares.

WHAT A BASELINE DOES NOT DO HERE, and why each is refused:

  * It does not change any exit code. `main()`'s `return 1 if hard or unver`
    is untouched. UNVERIFIABLE still exits non-zero — that is `6e86b46`'s rule
    and "cannot measure means pass" is the failure this project already fixed
    once. A baseline that softened an exit code would be the forbidden move.
  * It does not create a threshold. There is no "how far is too far" here at
    all: the comparison is equality of a verdict word, so there is no number to
    tune. This is the difference from the four UNAVAILABLE predecessors, which
    each lacked exactly that.
  * It does not rebuild itself silently. If the baseline file is missing the
    comparison reports MISSING and refuses to pass; see `compare()`. "Delete the
    baseline and the gate goes green" is the failure mode this guards.

WHY IT IS A SEPARATE MODULE AND NOT A `rule_*` FUNCTION
-------------------------------------------------------
`qa_layers._rule_functions()` reads every `rule_*` function off the AST, and
`tests/test_p18_qa_layer_partition.py` pins the resulting per-layer membership
in `PINNED_LAYERS`. A new rule function would have to be added to that pin,
which would make this file's arrival a change to a partition P18 owns and this
work order does not authorise. A baseline is also not a rule: it reports no
verdict of its own about an artefact, it compares two reports of the same
artefact. Keeping it out of the AST namespace keeps P18's partition untouched
and testable as it stands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: The two outcomes of a comparison, and the one that is not a pass. Named so a
#: caller cannot confuse "the baseline agreed" with "there was a baseline".
AGREES = 'AGREES'
DEVIATES = 'DEVIATES'
#: No baseline exists for this job, so nothing was compared. It is NOT AGREES:
#: a missing comparison must not read as a clean one, which is the same shape
#: of failure as the missing-props case `main()` already reports UNVERIFIABLE.
NO_BASELINE = 'NO_BASELINE'
#: A baseline exists but does not describe this artefact, so the two are not
#: comparable — same reasoning, opposite direction: the baseline is for another
#: job or another frame.
NOT_COMPARABLE = 'NOT_COMPARABLE'


@dataclass
class Deviation:
    """One rule whose verdict moved. Carries the two words, not a delta.

    A delta would be a number, and numbers are what this comparison refuses to
    use (see the module docstring): `font_size` moves 96.9% between two runs of
    one render. What moved is the VERDICT, and that is the whole fact.
    """

    rule: str
    was: str
    now: str

    def __str__(self) -> str:
        return f'{self.rule}: {self.was} -> {self.now}'


@dataclass
class Comparison:
    """The result of comparing one report against one baseline."""

    status: str
    deviations: list[Deviation] = field(default_factory=list)
    detail: str = ''

    @property
    def ok(self) -> bool:
        """True only when a comparison actually happened and found nothing.

        False for NO_BASELINE and NOT_COMPARABLE as well as DEVIATES, because a
        caller asking "is this fine" must not be told yes by a baseline that
        was never there.
        """
        return self.status == AGREES

    def __str__(self) -> str:
        if self.status == AGREES:
            return f'  [{self.status:12}] baseline   {self.detail}'
        if self.status == NO_BASELINE:
            return f'  [{self.status:12}] baseline   {self.detail}'
        if self.status == NOT_COMPARABLE:
            return f'  [{self.status:12}] baseline   {self.detail}'
        lines = [f'  [{self.status:12}] baseline   {self.detail}']
        lines += [f'                 {d}' for d in self.deviations]
        return '\n'.join(lines)


def verdict_profile(findings, drop: frozenset[str] = frozenset()) -> dict[str, str]:
    """rule -> verdict, the shape a baseline stores.

    `drop` removes rules whose verdict is a function of the ARTEFACT'S IDENTITY
    rather than its appearance. `contrast_frame` is the one that matters today:
    it is UNAVAILABLE on every frame, so storing it would store a constant and
    comparing it would be the "red for a constant" defect again. A rule that
    reports the same word on everything must not be in a baseline — the caller
    names them explicitly, so a new constant rule is excluded by review rather
    than by accident.
    """
    return {f.rule: f.verdict for f in findings if f.rule not in drop}


def compare(current: dict[str, str], baseline: dict[str, str] | None,
             subject: str = '') -> Comparison:
    """Compare a verdict profile against a stored one. Equality, not distance.

    `baseline` is None when there is nothing to compare against, and that is
    reported as NO_BASELINE rather than treated as agreement. This is the whole
    reason the module does not rebuild a missing baseline: a gate that writes
    its own reference the first time it is run passes on first sight of any
    input, so deleting the file would make the gate GREEN rather than red.
    """
    if baseline is None:
        return Comparison(NO_BASELINE, detail=(
            f'no baseline exists for {subject or "this job"}, so nothing was '
            f'compared. This is not a pass: a baseline that is absent cannot '
            f'vouch for the report. Record one deliberately '
            f'(--record-baseline), rather than letting a run create its own.'))
    if not baseline:
        return Comparison(NOT_COMPARABLE, detail=(
            f'the baseline file for {subject or "this job"} is empty, so there '
            f'is nothing to compare against'))
    if set(current) != set(baseline):
        only_cur = sorted(set(current) - set(baseline))
        only_base = sorted(set(baseline) - set(current))
        return Comparison(NOT_COMPARABLE, detail=(
            f'the baseline for {subject or "this job"} does not describe this '
            f'report: rules only in this run {only_cur}, only in the baseline '
            f'{only_base}. A baseline for one tool version cannot judge another'))
    devs = [Deviation(rule=r, was=baseline[r], now=current[r])
            for r in sorted(current) if current[r] != baseline[r]]
    if devs:
        return Comparison(DEVIATES, devs, detail=(
            f'{len(devs)} of {len(current)} verdicts moved away from the '
            f'baseline for {subject or "this job"}'))
    return Comparison(AGREES, detail=(
        f'all {len(current)} verdicts match the baseline for '
        f'{subject or "this job"}'))


def read_baseline(path: Path) -> dict[str, str] | None:
    """Load a baseline file, or None if there is not one.

    Returns None for BOTH "no such file" and "a file that is not a baseline", and
    `compare()` reports the two differently enough by telling the caller to
    record one — deliberately: an unreadable baseline is not silently replaced,
    because replacing it is how a corrupt file becomes a passing gate.
    """
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    verdicts = data.get('verdicts')
    if not isinstance(verdicts, dict) or not verdicts:
        return None
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in verdicts.items()):
        return None
    return verdicts


def write_baseline(path: Path, profile: dict[str, str], subject: str = '') -> Path:
    """Record a profile AS a baseline. An explicit act, never a side effect.

    Kept as its own function so the "record" path is visible in the call site:
    a report is written only when something asked for a baseline to be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {'subject': subject, 'verdicts': profile}, indent=1, ensure_ascii=True,
        sort_keys=True) + '\n', encoding='utf-8')
    return path
