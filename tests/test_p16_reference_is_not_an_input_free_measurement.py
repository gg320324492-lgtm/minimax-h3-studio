"""P16 — the reference film is not in this repository, and the verdict knows it.

WHAT THIS FILE IS
-----------------
`docs/UPGRADE_MASTER_PLAN.md:141` asks P16 for `reference_analyze.py` ->
`reference_analysis.json` over twelve dimensions (scene boundary / duration /
colour / layout / motion / camera / chart / font / transition / density /
brightness / beat), plus `24-40s` alignment. This file does NOT implement any of
it. It pins the finding that decides whether it can be implemented at all.

THE FINDING
----------
The reference film is not in the repository, is not on the disk locations a
bounded search reached, and — the part that is harder to undo — is not NAMED
anywhere it can be traced. The ledger still says the alignment was done
(`UPGRADE_PROGRESS.md:65` 「对齐参考片 24-40s 的四类代表 scene」 and `:85` 「参考片
24s」, both ✅). Those claims were measured, not quoted, and what the measurement
found is in `docs/P16_REFERENCE_BENCHMARK.md`: the alignment was done by eye and
by hand, and left behind no measurement that can be re-run.

So all twelve dimensions adjudicate B (undeterminable) and zero adjudicate A.
That is the fifth time this project has accepted "the measurement cannot produce
the separation the criterion needs" (collision, rule_duplicate,
rule_contrast_frame, flicker, and now the reference analysis itself), and it is
the same path P17 took.

THE QUESTION THIS FILE MUST ANSWER
----------------------------------
    "IF SOMEONE WROTE THE REFERENCE ANALYSIS TOMORROW, HOW WOULD THIS SUITE REACT?"

The answer must be a LOUD RED that asks for the verdict to be re-made, and it
must be that even when the analysis is a perfect, complete, well-formed
`reference_analysis.json` — because the thing that changed would be the
ADJUDICATION, not the file's syntax. The guard below therefore keys on the
artifact's EXISTENCE, not on its contents being well-formed, and says so in the
failure message: a `reference_analysis.json` appearing is not an achievement to
be celebrated, it is a twelve-dimension verdict that is now out of date.

That is the opposite of the failure mode this file is written to prevent. A guard
keyed on "the analysis file exists" would go GREEN the moment the analysis landed
and would never ask the twelve B verdicts to be re-examined — the same
always-green shape the project has been fooled by seven times.

WHY THE INPUT CLAIM IS ASSERTED BY SEARCH AND NOT BY PROSE
--------------------------------------------------------
The load-bearing negatives here are:

  * no tracked media file at all (`git ls-files` over mp4/mov/webm/mkv/avi/m4v);
  * `reference_analyze.py` and `reference_analysis.json` on disk and in git;
  * the two candidate material directories, measured rather than assumed.

Each is asserted by EXECUTING the search, and each search's own coverage is
asserted before its result — a sweep that scanned four files and found nothing is
not a sweep. The searches are bounded by an explicit skip list, and the skip list
names the directories that are excluded rather than the ones that are scanned, so
a new top-level directory cannot silently escape the search.

WHY NOT A CALIPER: NOTHING HERE IS A QUALITY JUDGEMENT
-----------------------------------------------------
No dimension is scored, no number is invented, and no threshold is proposed. The
twelve verdicts live in `docs/P16_REFERENCE_BENCHMARK.md` and this file guards
the three facts under them. A sixth invented metric is the failure mode, not the
fix.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: The verdict this file exists to hold. Named once so the witness test and every
#: other "is P16 still B?" check cannot drift apart — the P17 convention.
VERDICT_DOC = ROOT / 'docs' / 'P16_REFERENCE_BENCHMARK.md'

#: The twelve dimensions `docs/UPGRADE_MASTER_PLAN.md:141` names for P16.1. Read
#: from the ledger's own line so the list cannot rot into folklore.
P16_DIMENSIONS = (
    'scene 边界', '时长', '色彩', '布局', '运动', '相机',
    '图表', '字体', '转场', '密度', '亮度', 'beat',
)

#: Media suffixes a reference film would plausibly have. Broad on purpose: a
#: guard that only knows `.mp4` reports "no film" for a `.mov`, which is the
#: always-green shape one level up.
MEDIA_SUFFIXES = frozenset({'.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'})

#: Directories that are excluded from every on-disk search below, named so a new
#: top-level directory cannot slip past unnoticed. `experiments/` is deliberately
#: NOT excluded — it is where the one real reference analysis in this repository
#: lives, and excluding it would make the searches vacuous.
SKIP_DIRS = frozenset({
    'node_modules', '.git', '__pycache__', 'tools', 'out',
    'acestep-env', 'ffmpeg-7.1.1-full_build', '.remotion',
})

#: Directories too large to walk exhaustively (independent pipelines, tens of
#: thousands of files). Measured sizes: `ceo_mindread_ep01` is ~21,894 files.
#: `ceo_mindread_ep01` is walked where the question needs it (the 01_reference
#: subtree) but not from the root.
WALK_ROOTS = ('pipeline', 'studio', 'docs', 'experiments', 'tests', 'config')


def _tracked() -> list[str]:
    """`git ls-files`, or an empty list outside a git checkout.

    An empty result is treated as "cannot decide" by every caller, so this never
    silently turns a sweep into a vacuous pass.
    """
    try:
        proc = subprocess.run(['git', 'ls-files'], cwd=str(ROOT),
                              capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return proc.stdout.splitlines()


def _walk(roots=WALK_ROOTS):
    """Yield files under the given roots, skipping SKIP_DIRS.

    Yields the Path itself plus its parts-relative ROOT form so callers can
    count coverage without walking twice.
    """
    for rel_root in roots:
        base = ROOT / rel_root
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            parts = path.relative_to(ROOT).parts
            if any(p in SKIP_DIRS for p in parts):
                continue
            if path.is_file():
                yield path


def _analysis_artifacts(paths: list[str]) -> list[str]:
    """Which of `paths` are reference-analysis artifacts.

    ONE definition, called by both the real guard and its calibration. That is
    the whole point and it was measured the hard way: the first version of this
    file built the list INLINE inside the guard and wrote a SEPARATE helper for
    the calibration to exercise. Mutating the guard's inline list into a
    tautology therefore left the calibration green — MEASURED: all five
    neutering mutations (`trigger_always_true`, `media_always_true`,
    `selfcheck_always_true`, `absent_always_true`, `row_count_weakened`)
    survived with 7 passed and exit 0, because the calibration was testing code
    that no guard depended on. A calibration that tests a copy of the predicate
    is not a calibration.
    """
    return [p for p in paths
            if 'reference_analyze' in p.lower()
            or 'reference_analysis' in p.lower()]


def _media_files(paths: list[str]) -> list[str]:
    """Which of `paths` are media files. Same single-definition discipline."""
    return [p for p in paths if Path(p).suffix.lower() in MEDIA_SUFFIXES]


# ── 1. the trigger: the analysis does not exist, and its arrival is the red ───

def test_the_reference_analysis_does_not_exist_and_its_arrival_is_the_alarm():
    """THE load-bearing guard, and the one that answers the work order's question.

    P16.1 asks for `reference_analyze.py` -> `reference_analysis.json`. Both are
    absent, measured three ways: tracked in git, present on disk under the walked
    roots, and named by the ledger as outstanding.

    The failure message is the point of this test. A future reader who lands a
    complete analysis and sees this go red must be told that the ANALYSIS IS NOT
    WRONG — the VERDICT is out of date. `docs/P16_REFERENCE_BENCHMARK.md` holds
    twelve B verdicts that were decided because the input was missing; an input
    landing is exactly the event that retires them, and it must be re-made by
    someone, deliberately, rather than quietly satisfied by a file appearing.
    """
    tracked = _tracked()
    if not tracked:
        pytest.skip('not inside a git checkout; cannot decide')

    by_name = _analysis_artifacts(tracked)
    assert not by_name, (
        'A reference-analysis artifact is now TRACKED and this verdict is '
        'STALE, not wrong: '
        + ', '.join(sorted(by_name))
        + '\n\nP16 was adjudicated B for all twelve dimensions because the '
          'reference film was not in this repository (see '
          'docs/P16_REFERENCE_BENCHMARK.md). An input landing retires that '
          'reason — so the twelve verdicts must now be re-made against real '
          'measurements. Do not relax this assertion: it is the alarm, and '
          'relaxing it is how the next twelve B verdicts outlive the evidence '
          'that produced them. What must change is '
          'docs/P16_REFERENCE_BENCHMARK.md, re-adjudicated per dimension.')

    on_disk = sorted(
        p.relative_to(ROOT).as_posix()
        for name in ('reference_analyze.py', 'reference_analysis.json')
        for p in ROOT.rglob(name)
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    )
    assert not on_disk, (
        'A reference-analysis artifact exists on disk but is untracked '
        f'({on_disk}), so the verdict is stale in exactly the same way and the '
        'tracking is the smaller half of the problem. Re-adjudicate the twelve '
        'dimensions in docs/P16_REFERENCE_BENCHMARK.md.')

    # The ledger must still record P16 as outstanding. This is the corroborating
    # fact, not the primary one: docs/UPGRADE_PROGRESS.md is the ledger the
    # command window owns, and this assertion only says that the two documents
    # do not disagree about P16.
    ledger = (ROOT / 'docs' / 'UPGRADE_PROGRESS.md').read_text(encoding='utf-8')
    p16_block = ledger.split('## P16', 1)[1].split('\n## ', 1)[0] if '## P16' in ledger else ''
    assert p16_block, (
        'the ledger no longer has a P16 section. If P16 was renumbered or '
        'closed, this file is stale and its verdict must be revisited.')
    assert '⬜' in p16_block, (
        'the ledger no longer records P16 as outstanding (⬜). The twelve B '
        'verdicts are unchanged by an edit to the ledger, so either the '
        'verdicts were re-made — in which case this file must be rewritten — or '
        'the ledger stopped recording that the work is outstanding.')


# ── 3. the guard cannot be neutered into always-green ───────────────────────

def _predicate_is_not_vacuous(samples: list[str]) -> dict[str, int]:
    """How many of `samples` each ABSENCE PREDICATE marks as PRESENT.

    This is the self-check the neutering mutations measured the absence of.

    The problem it exists to solve: the headline assertions in this file are
    negatives about the repository (`no tracked media`, `no analysis file`). A
    negative assertion can be satisfied by a predicate that always reports
    "absent" — and that was MEASURED, twice, in two shapes:

      * mutating `assert not by_name` into `assert (not by_name) or True`
        survived the first version of this suite (6 passed, exit 0);
      * after a self-check was added, all five neutering mutations still
        survived (7 passed, exit 0) — because the self-check exercised a
        SECOND COPY of the predicates while the guards kept inline ones. A
        calibration that tests a copy is not a calibration.

    So it calls `_media_files` and `_analysis_artifacts` — the SAME functions the
    guards call, not reimplementations of them — over synthetic inputs that DO
    contain the artifacts. A predicate that can never fire fails here, before it
    can make the real guards meaningless.
    """
    return {'media': len(_media_files(samples)),
            'analysis': len(_analysis_artifacts(samples))}


def test_the_absence_predicates_can_detect_the_artifacts_they_claim_to():
    """Both halves, or the calibration is worthless.

    The POSITIVE half: given synthetic `git ls-files` output that DOES contain a
    film and DOES contain a reference analysis, both predicates must mark them
    found. A predicate that reports zero here reports zero forever, and the two
    real negatives built on it are then decorative.

    The NEGATIVE half: given the repository's own tracked list — measured, not
    assumed to be empty — the same predicates report zero. Without this, a
    predicate written to fire on everything would pass the calibration alone and
    the real guards would go permanently red for the wrong reason.
    """
    present = _predicate_is_not_vacuous([
        'pipeline/examples/showcase_demo.json',
        'assets/reference_film.mp4',
        'docs/reference_analysis.json',
        'tools/reference_analyze.py',
    ])
    assert present['media'] == 1, (
        f'the media predicate marked {present["media"]} of 1 synthetic film as '
        f'present. It cannot detect a committed film, so '
        f'test_no_tracked_media_file_exists_for_the_reference_film_to_be is '
        f'green forever and proves nothing.')
    assert present['analysis'] == 2, (
        f'the analysis predicate marked {present["analysis"]} of 2 synthetic '
        f'analysis files as present. It cannot detect the arrival it exists to '
        f'alarm on, so test_the_reference_analysis_does_not_exist_and_its_'
        f'arrival_is_the_alarm would stay green when the analysis lands — which '
        f'is the always-green failure this work order names.')

    tracked = _tracked()
    if not tracked:
        pytest.skip('not inside a git checkout; cannot decide')
    real = _predicate_is_not_vacuous(tracked)
    assert real['media'] == 0, (
        f'the real tracked list now holds {real["media"]} media file(s): '
        f'the real negative and this calibration disagree, and one of them is '
        f'wrong.')
    assert real['analysis'] == 0, (
        f'the real tracked list now holds {real["analysis"]} analysis file(s): '
        f'the real negative and this calibration disagree.')


def test_the_reference_analysis_alarm_is_wired_to_a_verdict_not_to_a_tautology(
        monkeypatch):
    """⚠️ THE guard against the always-green guard, and the mutation that forced it.

    MEASURED: five neutering mutations all survived an earlier version of this
    file with 7 passed and exit 0 — `trigger_always_true`
    (`assert not by_name` → `assert (not by_name) or True`), `media_always_true`,
    `selfcheck_always_true`, `absent_always_true`, `row_count_weakened`.

    The reason is not obvious and is the point of this test. The calibration
    above exercises `_analysis_artifacts`, which is the PREDICATE. The mutations
    neutralise the ASSERTION at the call site. Those are different lines, so a
    predicate-level check cannot see them: the predicate still works perfectly
    and the guard still ignores it. Any self-check that runs the helper is
    checking something the mutation did not touch.

    So this runs the GUARD FUNCTIONS THEMSELVES against a repository that
    contains what they claim to detect, and requires them to fail. The guards are
    ordinary functions; calling them directly and catching the AssertionError is
    the only way to ask "does this actually go red?" rather than "does this text
    look like it could?".

    This is the P17 convention — run the entry point, read the verdict, never
    read the source — applied to a test instead of a production script.

    NOTE WHAT THIS DOES NOT CLAIM. A determined editor can neuter this line too.
    Nothing inside one file can prevent that, and pretending otherwise is the
    error this project has made. What it does is make the neutering non-local:
    disabling the alarm now takes two edits in two places, and the second one is
    a test whose entire subject is the first.
    """
    # THE MODULE OBJECT ITSELF, by reference — not .
    # That call was the reason both witness tests were UNABLE to kill their
    # mutations: MEASURED,  and 
    # survived with 9 passed and exit 0 while the underlying guard rejected the
    # mutated document correctly in a standalone run.  under pytest is
    # the COLLECTION name of whichever file pytest loaded, so when a mutant is
    # collected as , 
    # imports  — but if a module of the
    # original name is already in sys.modules (it is, whenever the original file
    # was collected in the same session), the import returns THAT one and the
    # witness silently exercises the UNMUTATED guard. A self-check that tests
    # the wrong build of itself is the always-green failure one level up.
    mod = sys.modules[__name__]

    analysis_present = [
        'pipeline/examples/showcase_demo.json',
        'docs/reference_analysis.json',
        'tools/reference_analyze.py',
    ]
    media_present = analysis_present + [
        'assets/reference_film.mp4',
        'docs/other.mov',
    ]

    # ── the alarm must fire when an analysis lands ─────────────────────────
    monkeypatch.setattr(mod, '_tracked', lambda: analysis_present)
    with pytest.raises(AssertionError) as excinfo:
        mod.test_the_reference_analysis_does_not_exist_and_its_arrival_is_the_alarm()
    alarm = str(excinfo.value)
    assert 'STALE' in alarm, (
        f'the alarm fired but with an unhelpful message: {alarm[:300]}')
    assert 'reference_analysis.json' in alarm, (
        f'the alarm must NAME the artifact that landed, so a reader knows what '
        f'to re-adjudicate: {alarm[:300]}')
    assert 'docs/P16_REFERENCE_BENCHMARK.md' in alarm, (
        f'the alarm must point at the verdict that just went stale: '
        f'{alarm[:300]}')

    # ── the media negative must fire when a film is committed ──────────────
    # Padded past the guard's own `len(tracked) > 300` coverage assertion, so
    # the failure it produces is the media one and not a vacuity complaint.
    padded = media_present + [f'src/filler_{i:04d}.py' for i in range(400)]
    monkeypatch.setattr(mod, '_tracked', lambda: padded)
    with pytest.raises(AssertionError) as excinfo:
        mod.test_no_tracked_media_file_exists_for_the_reference_film_to_be()
    media_alarm = str(excinfo.value)
    assert 'TRACKED' in media_alarm, (
        f'the media guard fired on the wrong assertion: {media_alarm[:300]}')
    assert 'reference_film.mp4' in media_alarm, (
        f'the media guard must name the file it found: {media_alarm[:300]}')

    # ── and both must be QUIET on the repository as it actually is ─────────
    # Without this half the witness could be satisfied by guards that always
    # raise, which is the mirror image of the always-green failure.
    monkeypatch.undo()
    real = mod._tracked()
    if not real:
        pytest.skip('not inside a git checkout; cannot decide')
    mod.test_the_reference_analysis_does_not_exist_and_its_arrival_is_the_alarm()
    mod.test_no_tracked_media_file_exists_for_the_reference_film_to_be()


def test_the_verdict_table_guards_reject_a_document_that_no_longer_says_what_it_says(
        monkeypatch, tmp_path):
    """The two document-shape guards, run against documents that break them.

    Same reasoning as the alarm witness above, and the same thing MEASURED: the
    neutering mutations `row_count_weakened` and `selfcheck_always_true` both
    survived after the alarm witness was added, because that witness only covers
    the two absence predicates. These two guards are about the SHAPE of the
    verdict document and nothing else exercised them.

    So the guards are run against real, written documents — not strings, not
    monkeypatched readers — each one broken in a way the work order names:

      * a table missing a dimension's row (`dimension_dropped` survives a
        whole-document substring check, because the name still occurs in §5.1);
      * a summary claiming A=1 while the twelve rows still say B (the drift
        between the table and the summary it summarises);
      * a document claiming the alignment produced a reusable measurement,
        which is the opposite of the finding and must not be able to settle in
        quietly.

    A guard that cannot fail on these is a guard that is not there.
    """
    # THE MODULE OBJECT ITSELF, by reference — not .
    # That call was the reason both witness tests were UNABLE to kill their
    # mutations: MEASURED,  and 
    # survived with 9 passed and exit 0 while the underlying guard rejected the
    # mutated document correctly in a standalone run.  under pytest is
    # the COLLECTION name of whichever file pytest loaded, so when a mutant is
    # collected as , 
    # imports  — but if a module of the
    # original name is already in sys.modules (it is, whenever the original file
    # was collected in the same session), the import returns THAT one and the
    # witness silently exercises the UNMUTATED guard. A self-check that tests
    # the wrong build of itself is the always-green failure one level up.
    mod = sys.modules[__name__]

    if not VERDICT_DOC.is_file():
        pytest.skip('docs/P16_REFERENCE_BENCHMARK.md absent; nothing to guard')

    original = VERDICT_DOC.read_bytes()
    # Captured BEFORE any patch. Line 465 of an earlier version restored with
    # `monkeypatch.setattr(mod, 'VERDICT_DOC', VERDICT_DOC)` — but by then the
    # module global WAS the mutant, so the "quiet on the real document" half
    # re-read the third mutant and went red on a correct assertion with a
    # cause that had nothing to do with what it looked like.
    real_doc = VERDICT_DOC

    def _write(mutate, name: str) -> Path:
        text = original.decode('utf-8')
        mutated = mutate(text)
        assert mutated != text, 'the document mutation produced no change'
        # A DISTINCT file per mutation: the first version wrote all three to
        # `verdict.md`, so the third write clobbered the first two and the
        # "quiet on the real document" half at the end read the clobbered file.
        # That surfaced as a red on the correct assertion with a confusing
        # cause, which is the wrong-reason failure the work order warns about.
        p = tmp_path / f'verdict_{name}.md'
        p.write_bytes(mutated.encode('utf-8'))
        return p

    def drop_a_row(text: str) -> str:
        out = '\n'.join(l for l in text.split('\n')
                        if not l.startswith('| 9 | **转场**'))
        assert out != text, 'the row to drop moved; re-measure the anchor'
        return out

    def claim_an_a(text: str) -> str:
        out = text.replace('| **A：现在能分析** | **0** |',
                           '| **A：现在能分析** | **1** |')
        assert out != text, 'the summary row moved; re-measure the anchor'
        return out

    def claim_a_measurement(text: str) -> str:
        out = text.replace('没有任何测量', '已留下可复用测量')
        assert out != text, 'the phrase moved; re-measure the anchor'
        return out

    monkeypatch.setattr(mod, 'VERDICT_DOC', _write(drop_a_row, 'dropped'))
    with pytest.raises(AssertionError) as excinfo:
        mod.test_the_twelve_dimensions_are_all_adjudicated_and_none_is_an_a()
    # ⚠️ MEASURED WRONG-REASON FAILURE, TWICE, and the reason this assertion is
    # written the way it is. Version 1 pinned the message text
    # (`'not 12' in … or 'no row' in …`), which is satisfied by the row-count
    # failure only. Version 2 widened it to a list of three message shapes and
    # was still wrong, for the same reason: under `row_count_weakened`
    # (`assert len(rows) == 12` → `<= 12 or True`) the count check stops firing
    # and the guard falls through to the unadjudicated-dimension check, whose
    # message none of the three matched.
    #
    # BOTH times the guard was working and the mutation WAS being killed — the
    # witness was red for the wrong reason. What survives a dropped row is that
    # the guard says WHICH dimension lost its row, and that is what this asserts.
    # Pinning which internal assertion fires would break every time the guard's
    # internals are reordered, which is the "guard that fires on unrelated edits"
    # defect P13's file documents.
    dropped_alarm = str(excinfo.value)
    # ⚠️ THE THIRD wrong-reason failure of this assertion, and it is the one that
    # shows why the mechanism must not be pinned at all. Two facts about the two
    # builds of this guard:
    #
    #   unmutated  -> the ROW-COUNT assertion fires first and its message is
    #                 "parses to 11 adjudicated rows, not 12: [...]" — the list
    #                 of surviving rows, so the dropped one is ABSENT from it.
    #   row_count_weakened -> the count check passes and the UNADJUDICATED check
    #                 fires, whose message is "['转场'] appear in P16.1 but hold
    #                 no row" — the dropped dimension is NAMED.
    #
    # So the two messages share no content except that they both reject the
    # document. Any assertion that requires a specific phrase can only be
    # satisfied by one build, and will report a kill as a survivor or a survivor
    # as a kill. Verified by running both: the phrase check below passed on the
    # unmutated guard (where '转场' is absent from the message) and failed on the
    # mutant (where 'not 12' is absent).
    #
    # What is invariant across both builds, and is what this asserts: a dropped
    # row is REJECTED, and the message says the count is wrong or names what is
    # missing. Both are checked as a disjunction over CONCEPTS, never over one
    # build's wording.
    assert ('not 12' in dropped_alarm
            or '转场' in dropped_alarm), (
        f'a dropped verdict row must be rejected with a message that either '
        f'reports the wrong row count or names the dimension that lost it; '
        f'the message says neither: {dropped_alarm[:400]}')

    monkeypatch.setattr(mod, 'VERDICT_DOC', _write(claim_an_a, 'claims_a'))
    with pytest.raises(AssertionError) as excinfo:
        mod.test_the_twelve_dimensions_are_all_adjudicated_and_none_is_an_a()
    assert "'A': 1" in str(excinfo.value), (
        f'a summary claiming A=1 must be caught by the count parse: '
        f'{str(excinfo.value)[:300]}')

    monkeypatch.setattr(mod, 'VERDICT_DOC', _write(claim_a_measurement, 'claims_measurement'))
    with pytest.raises(AssertionError):
        mod.test_the_verdict_document_records_how_the_alignment_was_actually_done()

    # ── and quiet on the real document, or the witness proves nothing ───────
    monkeypatch.setattr(mod, 'VERDICT_DOC', real_doc)
    mod.test_the_twelve_dimensions_are_all_adjudicated_and_none_is_an_a()
    mod.test_the_verdict_document_records_how_the_alignment_was_actually_done()


def test_no_tracked_media_file_exists_for_the_reference_film_to_be():
    """The negative that decides all twelve dimensions, swept across the repo.

    `git ls-files` over a broad set of media suffixes returns EMPTY. There is no
    film in this repository for a reference analysis to analyse. Every other
    media file on the machine lives in gitignored output directories.

    The sweep's coverage is asserted first: a list of ten files that happened to
    contain no media is not evidence. `tracked` is asserted to be large enough
    that "zero media" is a statement about the repository rather than about an
    empty checkout.
    """
    tracked = _tracked()
    if not tracked:
        pytest.skip('not inside a git checkout; cannot decide')

    assert len(tracked) > 300, (
        f'git ls-files returned only {len(tracked)} paths; the sweep is '
        f'vacuous and "no tracked media" proves nothing')

    media = sorted(_media_files(tracked))
    assert not media, (
        f'{len(media)} media file(s) are now TRACKED, so a film may have been '
        f'committed: {media}. If one of them is the P16 reference film then the '
        f'twelve B verdicts must be re-made — see '
        f'docs/P16_REFERENCE_BENCHMARK.md. If it is unrelated media, extend '
        f'MEDIA_SUFFIXES or record the exclusion here, but do not leave this '
        f'assertion silently covering less.')


def test_the_walked_roots_exist_so_the_disk_sweep_is_not_vacuous():
    """The disk sweep's own coverage, asserted before any result is trusted.

    `ceo_mindread_ep01` is excluded from WALK_ROOTS because it is ~21,894 files
    across an independent pipeline, and sweeping it as source is the mistake the
    work order names. It is still checked DIRECTLY by
    `test_the_two_candidate_material_directories_are_not_the_film`, because that
    is where the one plausible-looking reference material actually is.
    """
    for rel in WALK_ROOTS:
        assert (ROOT / rel).is_dir(), (
            f'walked root {rel!r} is gone; the disk sweeps below would return '
            f'nothing and report "absent" for the wrong reason')

    scanned = list(_walk())
    assert len(scanned) > 200, (
        f'only {len(scanned)} files reachable under the walked roots; the '
        f'on-disk sweep is vacuous')


# ── 2. the two candidate material directories, measured not assumed ──────────

def test_the_two_candidate_material_directories_are_not_the_film():
    """Both directories the work order names, measured.

    Neither is the reference film, and the reasons are different, so both are
    recorded:

      * `ceo_mindread_ep01/01_reference` — 27 files, 4 mp4, 23 png. Inspected:
        live-action character reference sheets, generated BY MiniMax-H3's R2V
        workflow (its `gen_references.py` docstring says so). It is an INPUT to
        generating video, not a film to analyse.

      * `experiments/_ref_analysis` — the name matches, the content does not.
        11 extracted frames, all 1930x1080 (not 1920), plus `cuts.txt` with 87
        cut points spanning 264.567s of a ~4.5-minute film that
        `probe_liaozhai.py` names as 涛涛狐言《鬼新娘》 — a 1950s Chinese
        hand-drawn animation. Inspected frame by eye.

    This directory IS the trap this work order exists to catch: it is named
    `_ref_analysis`, it contains a genuine cut-detection output, and it is about
    a completely different film. A guard that swept "does any reference analysis
    exist" and stopped there would be green forever.
    """
    ceo = ROOT / 'ceo_mindread_ep01' / '01_reference'
    assert ceo.is_dir(), (
        'ceo_mindread_ep01/01_reference is gone. If it was removed as '
        'irrelevant that is a decision worth recording — it was the material '
        'this file names as NOT the film — but the claim must not lapse '
        'silently.')
    ceo_files = [f for f in ceo.rglob('*') if f.is_file()]
    assert len(ceo_files) == 27, (
        f'ceo_mindread_ep01/01_reference now holds {len(ceo_files)} files, not '
        f'the 27 measured on 2026-10-03. Either the film was added here — in '
        f'which case the twelve B verdicts must be re-made — or the '
        f'material changed and this file must be re-measured.')
    assert sum(1 for f in ceo_files if f.suffix == '.mp4') == 4, (
        'the mp4 count under ceo_mindread_ep01/01_reference changed: '
        f'{sorted(f.name for f in ceo_files if f.suffix == ".mp4")}')

    ref = ROOT / 'experiments' / '_ref_analysis'
    assert ref.is_dir(), 'experiments/_ref_analysis is gone; re-measure'
    cuts = ref / 'cuts.txt'
    assert cuts.is_file(), (
        'experiments/_ref_analysis/cuts.txt is gone. That file is the closest '
        'thing in this repository to a reference analysis, so its removal '
        'changes what this file is guarding and must be recorded, not absorbed.')

    values = [float(x) for x in
              cuts.read_text(encoding='utf-8').split()]
    assert len(values) == 87, f'cuts.txt holds {len(values)} lines, not 87'
    assert values == sorted(values), 'cuts.txt is no longer monotonic in time'
    assert abs(values[0] - 3.633333) < 1e-5 and abs(values[-1] - 268.2) < 1e-5, (
        f'cuts.txt now spans {values[0]}..{values[-1]}s; measured span was '
        f'3.633333..268.2s. A different film in this directory means the '
        f'verdicts must be re-made.')

    frames = sorted(ref.glob('f_*.png'))
    assert len(frames) == 11, f'{len(frames)} extracted frames, not 11'
    from PIL import Image
    sizes = set()
    for f in frames:
        with Image.open(f) as im:
            sizes.add(im.size)
    assert sizes == {(1930, 1080)}, (
        f'extracted reference frames are {sorted(sizes)}, not all 1930x1080. '
        f'1930 is not 1920: these frames were not taken from a 1080p product '
        f'film, which is one of the reasons this material is not it.')


def test_the_twelve_dimensions_are_all_adjudicated_and_none_is_an_a():
    """The verdict table is complete, and it says what it measured.

    Two things are asserted:

      * all twelve dimensions `UPGRADE_MASTER_PLAN.md:141` names appear in the
        verdict document, so a dimension cannot quietly drop out of the record;
      * the summary counts A / B / C, and A is zero.

    The A-is-zero assertion is the one with teeth. If somebody fills in the
    table, this goes red and the failure message says what filling it in
    requires: an input, and for five dimensions an instrument or a criterion
    that does not exist yet either way. It is not a request for a number.
    """
    if not VERDICT_DOC.is_file():
        pytest.skip('docs/P16_REFERENCE_BENCHMARK.md absent; nothing to guard')
    text = VERDICT_DOC.read_text(encoding='utf-8')

    # ⚠️ MEASURED DEFECT IN AN EARLIER VERSION OF THIS ASSERTION, and the second
    # one this file found in itself. It read
    # `missing = [d for d in P16_DIMENSIONS if d not in text]` — a
    # whole-document substring membership test. A mutation that removed a
    # dimension's verdict ROW from the table SURVIVED it (6 passed, exit 0),
    # because the dimension's name also occurs in §5.1's prose: 「转场（schema
    # 无枚举）」 names it without adjudicating it. A dimension was still
    # discussed; its verdict was gone; the guard said the record was complete.
    #
    # So membership is now asserted over the VERDICT TABLE'S ROWS, which is where
    # a verdict actually lives, and not over the whole document.
    table = text.split('| # | 维度 | 裁定 |', 1)[1].split('\n\n', 1)[0] \
        if '| # | 维度 | 裁定 |' in text else ''
    assert table, (
        'the verdict document no longer has the twelve-dimension table '
        '(header `| # | 维度 | 裁定 |`). The verdict moved somewhere this test '
        'cannot see; teach it the new location rather than letting the '
        'membership check lapse into scanning prose.')

    # Row shape: `| <n> | **<dimension>** | **<verdict>** | …`. `beats` is
    # ASCII in the table while the rest are CJK, so both spellings are accepted
    # for it and no other.
    rows: dict[str, str] = {}
    for line in table.splitlines():
        m = re.match(r'\|\s*\d+\s*\|\s*\*\*(?P<dim>[^*]+)\*\*\s*\|'
                     r'\s*\*\*(?P<verdict>[ABC])\*\*\s*\|', line)
        if m:
            rows[m.group('dim').strip()] = m.group('verdict')
    assert len(rows) == 12, (
        f'the verdict table parses to {len(rows)} adjudicated rows, not 12: '
        f'{sorted(rows)}. A dimension whose row lost its verdict, lost its name '
        f'or changed shape has not been adjudicated — it has been dropped.')

    # Every dimension P16.1 names must hold a verdict row under its own name.
    # `beat` is written 「beat」 in both places; the CJK dimension names are
    # matched by the exact string from P16_DIMENSIONS.
    unadjudicated = [d for d in P16_DIMENSIONS if d not in rows]
    assert not unadjudicated, (
        f'{unadjudicated} appear in P16.1 but hold no row in the verdict table '
        f'({sorted(rows)}). Naming a dimension in prose is not adjudicating it — '
        f'each one needs its own row carrying its own verdict.')

    # ⚠️ MEASURED DEFECT IN AN EARLIER VERSION OF THIS TEST, and the reason the
    # count check below is a PARSE rather than a substring test. It read
    # `assert '**0**' in summary and '**12**' in summary`, which a mutation
    # turning the A count from 0 to 1 SURVIVED (6 passed, exit 0) — because the
    # summary table contains `**0**` on the C row too, so both substrings were
    # still present. Two `**0**` rows, one substring.
    #
    # What this asserts now is each verdict's count separately, read out of its
    # own table row, so A=0 cannot be satisfied by C=0 and B=12 cannot be
    # satisfied by any other number in the section. The count is also cross-
    # checked against the rows parsed above, so the summary cannot drift away
    # from the table it summarises.
    summary = text.split('### 4.1', 1)[-1] if '### 4.1' in text else ''
    assert summary, 'the verdict document has no summary section (### 4.1)'

    counts: dict[str, int] = {}
    for line in summary.splitlines():
        m = re.match(r'\|\s*\*\*(?P<verdict>[ABC])：[^*]*\*\*\s*\|\s*'
                     r'\*\*(?P<count>\d+)\*\*\s*\|', line)
        if m:
            counts[m.group('verdict')] = int(m.group('count'))
    assert set(counts) == {'A', 'B', 'C'}, (
        f'the A/B/C summary rows are no longer parseable as {{A, B, C}} counts; '
        f'parsed {counts}. The table shape changed, so teach this test the new '
        f'shape rather than letting the count check lapse.')
    assert counts == {'A': 0, 'B': 12, 'C': 0}, (
        f'the A/B/C summary now reads {counts}, not A=0, B=12, C=0. If a '
        f'dimension was re-adjudicated as A or C, that is a real change of fact '
        f'and this file must be rewritten to say so — with the input and the '
        f'measurement that justified it, not with a number that moved.')

    # The summary must agree with the table it summarises, counted from the rows
    # parsed above rather than from the table's own numbering. This is what stops
    # the two from drifting apart: a summary edited to A=1 while the twelve rows
    # all still say B is caught twice, and a row flipped to A while the summary
    # is left alone is caught here.
    from_rows = {v: list(rows.values()).count(v) for v in 'ABC'}
    assert from_rows == counts, (
        f'the summary says {counts} but the twelve verdict rows tally to '
        f'{from_rows}. One of the two was edited without the other; whichever is '
        f'right, the disagreement means the record does not know what it says.')


def test_the_verdict_document_records_how_the_alignment_was_actually_done():
    """The ledger says 「对齐参考片」 twice and marks both ✅; the record must
    disagree with the part that is not reproducible.

    `UPGRADE_PROGRESS.md:65` and `:85` are the claims this work order was asked
    to verify. The finding is that the alignment was done by eye and by hand and
    left no re-runnable measurement — so the verdict document must say so, in
    those terms, and must not assert that a reusable measurement exists.

    The negative half matters more than the positive half: if someone later adds
    「可复用测量」 or claims the alignment is reproducible, this goes red. A guard
    that only checked the document was written would let the opposite claim slip
    in just as silently.
    """
    if not VERDICT_DOC.is_file():
        pytest.skip('docs/P16_REFERENCE_BENCHMARK.md absent; nothing to guard')
    text = VERDICT_DOC.read_text(encoding='utf-8')

    for phrase in ('人眼', '手工调', '没有任何测量'):
        assert phrase in text, (
            f'the verdict document no longer says {phrase!r}. The finding under '
            f'this guard is that the alignment was done by eye and by hand with '
            f'no re-runnable measurement; if that finding changed, it changed '
            f'because evidence turned up, and the change belongs on the record.')

    for forbidden in ('可复用的测量存在', '对齐可复现', 'reference_analysis.json 已'):
        assert forbidden not in text, (
            f'the verdict document now claims {forbidden!r}. The twelve B '
            f'verdicts rest on there being no input and no measurement; a claim '
            f'that one exists must be backed by the artifact and this guard must '
            f'be rewritten from it.')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))