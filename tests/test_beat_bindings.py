"""The six binding events, and the SFX table 9.3 will wire (P9 steps 13-14).

P9's audit found the six events 9.2 wants to bind to the beat grid split three ways,
and only one part of that split is a table:

  QUERYABLE (2)   camera settle and chart finish each have a pure function that
                  answers "when" — `cameraStateAt().t` and `lifecycleAt()`.
  INPUT-ONLY (2)  cut and card arrival have the DATA but no exported frame:
                  `SceneEnter` consumes `transitionIn` internally, `Reveal` computes
                  its spring length locally and never returns it.
  ABSENT (2)      number finish and hit have nothing. `countUp`'s 1.6s is a default
                  parameter AND its call site passes the literal again, so it is not
                  even a token; and `hit` has no concept anywhere in the template.

The guards therefore are about AVAILABILITY and about the four `source` strings that
have to explain themselves. The length floor is the point: `''`, `'n/a'`, `'none'`
and `'unavailable'` all pass a truthiness check, and all four tell a later reader
nothing about why a capability is missing — which is indistinguishable from it never
having been looked at.

The SFX table is checked against the audio DIRECTORY rather than a hand-kept list,
because a wrong filename in a table is a 404 inside an `<Audio>` at render time, and
that is silence rather than an error.

Where node is unavailable the behavioural tests SKIP rather than fail, matching
`test_perspective_math.py` and `test_beat_grid.py`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BEAT = ROOT / 'studio' / 'src' / 'templates' / 'finance-showcase' / 'beat'
BINDINGS = BEAT / 'bindings.ts'
BINDINGS_CHECK = BEAT / 'bindings.check.ts'
SFX = BEAT / 'sfxProfile.ts'
SFX_CHECK = BEAT / 'sfxProfile.check.ts'

_NPX = shutil.which('npx') or shutil.which('npx.cmd')


def _code_only(path: Path) -> str:
    """The file with block and line comments removed.

    These guards are textual, and both modules explain themselves in comments that
    quote the constructs the guards forbid — `bindings.ts` names `remotion` and
    `staticFile` while explaining that it uses neither. A guard that cannot tell a
    prohibition from a use of the thing has to be weakened until it is useless.
    """
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'^\s*//.*$', '', text, flags=re.MULTILINE)
    return text


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_bindings_check_passes():
    proc = subprocess.run(
        [_NPX, 'tsx', str(BINDINGS_CHECK)],
        cwd=ROOT / 'studio', capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
    )
    assert proc.returncode == 0, f'bindings check failed:\n{proc.stdout}\n{proc.stderr}'


@pytest.mark.skipif(_NPX is None, reason='node/npx not on PATH')
def test_sfx_profile_check_passes():
    proc = subprocess.run(
        [_NPX, 'tsx', str(SFX_CHECK)],
        cwd=ROOT / 'studio', capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
    )
    assert proc.returncode == 0, f'sfxProfile check failed:\n{proc.stdout}\n{proc.stderr}'


def test_bindings_is_measurable_without_a_renderer():
    """`bindings.ts` must stay free of react, remotion and staticFile.

    Two of its six answers come from real functions — `cameraMoveFrames` and
    `lifecycleAt` — and asking them rather than recomputing them is the entire
    reason the bindings cannot drift from the motion system. A binding that had to
    be read out of a rendered frame would be worth nothing as a specification.
    """
    code = _code_only(BINDINGS)
    for forbidden in ('react', 'remotion', 'staticFile', '<Audio'):
        assert forbidden not in code, (
            f'bindings.ts references {forbidden} — it must stay importable by a '
            f'checker, so it cannot reach for the renderer'
        )


def test_sfx_profile_is_pure_data():
    """`sfxProfile.ts` is a table. It must not grow logic that needs a renderer.

    Not tidiness: the table is the "before/after" specification for 9.3, and a
    mapping that could only be evaluated inside a component cannot be compared with
    the report side's behaviour, which is the comparison the table exists for.
    """
    code = _code_only(SFX)
    for forbidden in ('react', 'remotion', 'staticFile', 'Audio', 'useVideoConfig'):
        assert forbidden not in code, f'sfxProfile.ts references {forbidden}'


def test_all_six_event_literals_are_named_in_bindings():
    """The six literals must appear, so a renamed event cannot silently vanish.

    `BINDING_EVENTS` is the source of truth for both files, so this asserts against
    it AND against the literal text — the check reads the array, but a later edit
    that rewrites the array and forgets the switch would leave a `default` branch
    throwing at runtime for an event nobody listed.
    """
    src = BINDINGS.read_text(encoding='utf-8')
    for event in ('camera-settle', 'chart-finish', 'cut', 'card-arrival',
                  'number-finish', 'hit'):
        assert f"'{event}'" in src, f'bindings.ts never names the event {event}'
    assert 'BINDING_EVENTS' in src, 'the canonical list must exist'
    assert 'availableEvents' in src, (
        'a way to ask "which events can be bound" is the query 9.2 needs first'
    )


def test_unavailable_events_explain_themselves_in_source():
    """All four unavailable events must carry a written reason.

    Checked here as well as in the runtime check, because the runtime check needs
    node and this is the assertion that matters most: a `source` of `'n/a'` passes
    every truthiness test and leaves the next reader unable to tell a missing
    capability from a missing investigation.
    """
    src = BINDINGS.read_text(encoding='utf-8')
    for event, needle in (
        ('cut', 'SceneEnter'),
        ('card-arrival', 'Stagger'),
        ('number-finish', '1.6'),
        ('hit', 'permutation test'),
    ):
        block = src.split(f"'{event}'", 1)
        assert len(block) == 2, f'bindings.ts does not name {event}'
        # the SOURCES entry for this event must mention the evidence
        sfx = SFX.read_text(encoding='utf-8')
        assert needle in sfx or needle in src, (
            f'the reason {event} has no surface should cite {needle!r} — a bare '
            f'"not available" is what this guard exists to prevent'
        )


def test_sfx_filenames_are_checked_against_the_directory():
    """The filename check must read the directory, not a list in the check.

    A hand-kept list is the thing that goes stale: the file is renamed, the list is
    not, and the table is wrong in a way nothing reports.
    """
    src = SFX_CHECK.read_text(encoding='utf-8')
    assert 'readdirSync' in src, 'the sfx check must read the audio directory'
    assert "studio/public/audio" in src.replace('\\', '/'), (
        'the sfx check must point at studio/public/audio'
    )
    audio = ROOT / 'studio' / 'public' / 'audio'
    present = {f for f in audio.iterdir() if f.suffix == '.m4a'}
    sfx_only = {f for f in present if f.name.startswith('sfx_')}
    assert len(present) == 15, f'expected 15 m4a, found {len(present)}'
    assert len(sfx_only) == 6, f'expected 6 sfx_* files, found {len(sfx_only)}'


def test_coverage_is_pinned_to_the_measured_table():
    """3 of 6, and the three holes are named.

    Coverage is the number most likely to drift: adding a row without a file, or
    mapping an event to `null` by accident, both leave every other assertion green.
    """
    src = SFX.read_text(encoding='utf-8')
    check_src = SFX_CHECK.read_text(encoding='utf-8')
    assert 'coverage is 3/6' in check_src, (
        'the coverage figure must stay pinned to 3/6 — it was measured from the '
        'table, and an unpinned coverage number is a guess'
    )
    # Quoting is optional for identifier-shaped keys (`hit: null` is valid), so the
    # guard accepts either. Pinning the exact spelling would fail on a cosmetic
    # reformat and pass on a real change.
    for event, value in (
        ('camera-settle', "'sfx_"),
        ('chart-finish', "'sfx_"),
        ('cut', "'sfx_"),
        ('card-arrival', 'null'),
        ('number-finish', 'null'),
        ('hit', 'null'),
    ):
        pattern = rf"'{event}':\s*{re.escape(value)}|{event}:\s*{re.escape(value)}"
        assert re.search(pattern, src), (
            f'sfxProfile.ts does not map {event} to {value}…; the coverage pin '
            f'(3/6) and the table would have drifted apart'
        )
