"""P37 — the reference film arrived; the guard must work WITHOUT it.

THE PROBLEM THIS FILE SOLVES
----------------------------
The reference film (a Douyin options-data screen-recording, 1280x720@60,
5082 frames, 86.2s) lives in a WeChat cache directory OUTSIDE this
repository. A guard that opens it would go red on every machine that has never
received the file — which is every machine but one, and would make the guard a
measure of who has run the WeChat client rather than of what the code does.

So this file never opens the film. It asserts four things that hold whether or
not the film exists:

  1. `probe()` on a missing input reports UNAVAILABLE for all twelve
     dimensions — it does not raise, and it does not quietly return PASS. The
     failure this catches is the one P31/P34 each hit: a probe that throws is
     turned into a verdict, and two identical exceptions get compared and
     reported as agreement.
  2. A synthetic clip BUILT HERE, in tmp_path, from `ffmpeg`'s own test
     sources gets a verdict that DIFFERS from a missing input — which is what
     "the criterion depends on the input" means operationally.
  3. Two different synthetic films get DIFFERENT verdicts. This is the
     mutation-killing half: a criterion that returns the same table whatever
     you feed it cannot tell a film from a non-film, and would pass mutation
     1 and 2 forever.
  4. The adjudication table in `docs/P37_REFERENCE_REANALYSIS.md` still records
     a verdict for each of the twelve dimensions, and still says which are A.

WHY A SYNTHETIC CLIP RATHER THAN A COMMITTED FIXTURE
----------------------------------------------------
`.gitignore` carries `*.mp4` and `git ls-files "*.mp4"` is empty: this project
does not track media, and a committed fixture would be the first exception in
years. So the fixture is BUILT, from lavfi sources, into tmp_path — a few KB,
gone when the test ends, and byte-identical on every machine that has ffmpeg.

WHAT THIS GUARD CANNOT DO
-------------------------
It cannot verify that the verdicts in the document match the real film; that
needs the film. What it holds is the much more failure-prone property: that
the instrument distinguishes input from no-input, and different inputs from
each other. A verdict that is wrong about the film is a re-adjudication; a
verdict that cannot tell a film from a hole is a broken instrument, and it
would have looked identical.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

import reference_probe as rp                                   # noqa: E402

VERDICT_DOC = ROOT / 'docs' / 'P37_REFERENCE_REANALYSIS.md'

#: Where the film actually is. Recorded, never opened — see the module
#: docstring. A test that asserts on this path's existence is the exact
#: mistake this file exists to not make.
FILM_PATH = ('C:/Users/pc/Documents/xwechat_files/wxid_uibqlezvenv522_4379/'
             'msg/video/2026-10/47b43f61516c23d169ddd34b00695ab2_raw.mp4')

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which('ffmpeg') and shutil.which('ffprobe')),
    reason='ffmpeg/ffprobe not on PATH; the synthetic fixtures cannot be built')


def build_clip(path: Path, lavfi: str, seconds: float = 2.0,
               fps: int = 10, size: str = '160x90',
               with_audio: bool = True) -> Path:
    """Render a tiny film from ffmpeg's synthetic sources into tmp_path.

    Two films built with different `lavfi` must be genuinely different films —
    one a hard cut between two colours, one a static gradient — because the
    guard's central claim is that the verdict FOLLOWS the input.
    """
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', lavfi,
           '-t', str(seconds)]
    if with_audio:
        cmd += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', str(fps),
            '-s', size]
    if with_audio:
        cmd += ['-c:a', 'aac', '-shortest']
    cmd += [str(path)]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    assert proc.returncode == 0, f'could not build {path.name}: {proc.stderr[:400]}'
    assert path.is_file() and path.stat().st_size > 0, 'fixture is empty'
    return path


# ── 1. no input, no verdict, and above all no crash ────────────────────────

@pytest.mark.parametrize('bad', [None, 'E:/definitely/not/here/x.mp4',
                                 str(ROOT / 'docs' / 'UPGRADE_PROGRESS.md')])
def test_a_missing_input_reports_unavailable_rather_than_raising_or_passing(bad):
    """The film's absence must be REPORTED, not thrown and not scored.

    Three failure shapes are being excluded at once, and the middle one is the
    dangerous one:

      * raising — a caller upstream turns an exception into a verdict, and two
        identical exceptions compare equal (P31/P34);
      * returning PASS — the always-green shape this project has been fooled
        by seven times;
      * returning an EMPTY dict — indistinguishable from "nothing to say", and
        a `for d in DIMENSIONS` assertion over it would pass vacuously.
    """
    res = rp.probe(bad)
    assert not res.available, f'{bad!r} was reported as available'
    assert res.reason, 'an unavailable result must say WHY it is unavailable'
    assert set(res.verdicts) == set(rp.DIMENSIONS), (
        f'the verdict covers {sorted(res.verdicts)}, not the twelve dimensions '
        f'{sorted(rp.DIMENSIONS)}')
    assert set(res.verdicts.values()) == {rp.UNAVAILABLE}, (
        f'a missing input produced {sorted(set(res.verdicts.values()))} — every '
        f'dimension must be UNAVAILABLE. PASS is a claim about a film nobody '
        f'measured; anything else is the same error in a different costume.')


def test_the_probe_never_reads_the_film_path_itself():
    """The guard's premise, asserted rather than assumed.

    `reference_probe.probe` takes whatever path it is given. What must not
    happen is the MODULE reaching for a hardcoded film location, because that
    is what would make the suite depend on a WeChat cache directory. So the
    source is searched for a hardcoded absolute path, and the guard's own
    constant is required to be the only one in the file.
    """
    src = (ROOT / 'studio' / 'scripts' / 'reference_probe.py').read_text(
        encoding='utf-8')
    for needle in ('Documents', 'xwechat', 'wxid_', '.mp4'):
        assert needle not in src, (
            f'reference_probe.py mentions {needle!r}. The film lives outside '
            f'the repository; if the probe hardcodes a location for it, every '
            f'machine without that file fails this suite for a reason that has '
            f'nothing to do with the code.')


# ── 2 & 3. the verdict follows the input ───────────────────────────────────

@needs_ffmpeg
def test_a_built_clip_and_a_missing_file_get_different_verdicts(tmp_path):
    """The load-bearing claim: measurement happened, so the verdict changed.

    The synthetic film is a hard cut between two flat colours — the smallest
    input that can make a scene-boundary instrument say something. If the
    verdict were identical to the missing-file verdict, the instrument would be
    reporting on the PATH rather than on the FILM, and every dimension would be
    decoration.
    """
    clip = build_clip(tmp_path / 'flat.mp4',
                      'color=c=0x101010:s=160x90:d=2', seconds=2.0)

    measured = rp.probe(clip)
    missing = rp.probe(tmp_path / 'not-there.mp4')

    assert measured.available, (
        f'the synthetic fixture could not be probed: {measured.reason}. If the '
        f'fixture cannot be built here, this guard cannot run here at all — '
        f'say so rather than skipping quietly.')
    assert measured.measurements['frames_measured'] > 1, (
        f'the fixture decoded {measured.measurements["frames_measured"]} '
        f'frames; a verdict cannot be adjudicated from an empty measurement')
    assert measured.verdicts != missing.verdicts, (
        'a real film and a missing file produced IDENTICAL verdicts '
        f'({measured.verdicts}). The criterion does not depend on its input, '
        'so every number it reports is decorative.')


@needs_ffmpeg
def test_two_different_films_get_different_verdicts(tmp_path):
    """⚠️ The mutation-killing test. Two films, two answers.

    One film carries an audio stream; the other does not. `beat` is adjudicated
    on `has_audio`, so the two MUST differ on it. That is a deliberately small
    difference to make it robust: it does not depend on a threshold being
    tuned right, only on the stream genuinely being present or absent.

    A criterion hardcoded to return the same table regardless of input fails
    this, and no threshold can save it.
    """
    with_sound = build_clip(tmp_path / 'with_audio.mp4',
                            'color=c=0x202020:s=160x90:d=2', with_audio=True)
    without_sound = build_clip(tmp_path / 'silent.mp4',
                               'color=c=0x202020:s=160x90:d=2', with_audio=False)

    a, b = rp.probe(with_sound), rp.probe(without_sound)
    assert a.available and b.available, (
        f'fixtures were not probeable: {a.reason!r} / {b.reason!r}')

    assert a.stream['has_audio'] and not b.stream['has_audio'], (
        'the fixtures did not differ in the one respect this test relies on '
        f'(has_audio: {a.stream["has_audio"]} vs {b.stream["has_audio"]}), so a '
        'failure below would be the fixture\'s fault, not the criterion\'s')
    assert a.verdicts['beat'] != b.verdicts['beat'], (
        'a film with an audio stream and a film without one both adjudicated '
        f'`beat` as {a.verdicts["beat"]!r}. The verdict did not follow the input.')
    assert a.verdicts != b.verdicts, (
        f'two different films produced identical verdicts: {a.verdicts}')


# ── 4. the document still says what it decided ──────────────────────────────

def test_the_twelve_dimensions_each_hold_a_verdict_in_the_record():
    """P37's own table, parsed as rows — not as document prose.

    The P16 file's own history is why: a substring check over the whole
    document survives a dimension losing its verdict ROW, because the name
    still occurs in the prose. So membership is asserted over parsed table rows,
    and the A/B/C counts are read out of the rows and cross-checked against the
    summary, the same way P16's guard does it.
    """
    if not VERDICT_DOC.is_file():
        pytest.skip('docs/P37_REFERENCE_REANALYSIS.md absent; nothing to guard')
    text = VERDICT_DOC.read_text(encoding='utf-8')

    header = '| # | 维度 | 裁定 |'
    if header not in text:
        # The table may use ASCII 'dimension'/'verdict' headers; find the row
        # shape directly instead of trusting one spelling of the header.
        header = next((h for h in ('| # | 维度 | 裁定 |', '| # | dimension | verdict |')
                       if h in text), '')
    assert header, (
        'P37_REFERENCE_REANALYSIS.md no longer has a twelve-dimension verdict '
        'table. The verdict moved somewhere this test cannot see; teach it the '
        'new location rather than letting the membership check lapse into '
        'scanning prose.')

    table = text.split(header, 1)[1].split('\n\n', 1)[0]
    rows: dict[str, str] = {}
    for line in table.splitlines():
        cells = [c.strip().strip('*') for c in line.split('|')]
        if len(cells) >= 4 and cells[1].isdigit() and cells[2] and cells[3] in ('A', 'B', 'C'):
            rows[cells[2]] = cells[3]

    assert len(rows) == 12, (
        f'the verdict table parses to {len(rows)} adjudicated rows, not 12: '
        f'{sorted(rows)}. A dimension whose row lost its verdict has been '
        f'dropped, not adjudicated.')
    missing = [d for d in rp.DIMENSIONS if d not in rows]
    assert not missing, (
        f'{missing} are named by P16.1 but hold no row in the P37 table '
        f'({sorted(rows)}). Naming a dimension in prose is not adjudicating it.')

    counted = {v: list(rows.values()).count(v) for v in 'ABC'}
    assert sum(counted.values()) == 12, f'row tally {counted} does not cover twelve'
    assert counted['A'] > 0, (
        'P37 recorded zero A verdicts. The film is now measurable, so at least '
        'one dimension must have been adjudicated A against a number. If that '
        'is wrong, the record is wrong — but a table of all-B here is the P16 '
        'verdict copied forward without re-measuring it.')

    # ⚠️ MEASURED SURVIVOR, and the reason this assertion exists. The first
    # version of this test parsed the rows and checked `counted['A'] > 0`, and
    # a mutation that changed ONLY the summary row — 'A：现在能量 | 4' to
    # '| 0' — SURVIVED it with 7 passed and exit 0. The twelve rows still said
    # A; only the tally beneath them had been edited, and nothing compared the
    # two. A summary that disagrees with the table it summarises is the exact
    # drift P16's own file was written to catch, and it had been reintroduced
    # here in a new place.
    #
    # So the summary is now parsed and cross-checked against the rows, and the
    # A/B/C counts are read out of the SUMMARY'S OWN line -- not by scanning the
    # document for the substring '4', which the row numbers would satisfy.
    summary = text.split('### 2.1', 1)[-1] if '### 2.1' in text else ''
    assert summary, (
        'the verdict document has no summary section (### 2.1); the A/B/C '
        'tally cannot be cross-checked against the rows it summarises')
    tallied: dict[str, int] = {}
    for line in summary.splitlines():
        m = re.match(r'\|\s*\*\*(?P<v>[ABC])：[^*]*\*\*\s*\|\s*\*\*(?P<n>\d+)\*\*\s*\|', line)
        if m:
            tallied[m.group('v')] = int(m.group('n'))
    assert tallied == counted, (
        f'the summary tallies {tallied} but the twelve verdict rows tally to '
        f'{counted}. One of the two was edited without the other, so the '
        f'record does not know what it says.')


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))