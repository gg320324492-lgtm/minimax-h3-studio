"""The webpack bundle must not survive the process that made it (P11, disk root cause).

118 of them once filled a C: TEMP to 46 GB. Each render leaked one ~800 MB copy
of studio/public, and the cause was not "Remotion is untidy" but a specific pair
of facts in the bundler's source:

  * `bundle()` with no `outDir` calls
    `mkdtemp(join(os.tmpdir(), 'remotion-webpack-bundle-'))`
  * `prepareOutDir` creates that directory and NEVER deletes it — with or
    without an explicit `outDir`

The second fact is the one that makes the obvious fix wrong. Passing an
`outDir` only MOVES the leak, so "point it at E:" stops the disk filling but
leaves 800 MB of garbage per render forever. Both halves are needed, and this
file asserts each half separately.

These are static assertions on render.mjs, which is the honest scope available
in a test suite: they cannot prove the directory is removed, only that nothing
in the source can remove it. The behavioural half was measured by hand on this
same commit — HEAD's render.mjs left 1 bundle in TEMP per run, the fixed one
left 0, and sampling during a render showed the scratch dir really reaching
800 MB and dropping to 0 at exit. That measurement is what these assertions
encode; they are the cheap regression guard on it, not a substitute.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'studio' / 'scripts'))

RENDER = ROOT / 'studio' / 'bin' / 'render.mjs'


def _src() -> str:
    return RENDER.read_text(encoding='utf-8')


def _code() -> str:
    """render.mjs with comments stripped.

    Comments in this file explain each guard by naming the exact token it
    looks for, which means a naive substring search over the raw source finds
    that token in the prose even when the code it describes is gone. One
    mutation (fixed path instead of mkdtemp) survived a guard written that way.
    """
    s = _src()
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//.*', '', s)


def test_the_bundler_is_given_a_directory_we_control():
    """Without outDir the destination is os.tmpdir() and nobody chose it."""
    s = _code()
    assert 'bundle({' in s, 'the bundle call moved or was renamed — re-find it'
    call = s.split('bundle({', 1)[1].split('});', 1)[0]
    assert 'outDir' in call, (
        'bundle() takes no outDir, so Remotion mkdtemps into os.tmpdir() — '
        'on this machine that is C:, the one drive that ran out of space'
    )


def test_the_scratch_directory_is_per_run_not_a_fixed_path():
    """A fixed path would be shared by two concurrent renders.

    The A/B and audit paths render in parallel, and a shared outDir means one
    run's cleanup deletes the bundle another run is still serving from.

    Matched against executable code rather than the whole file on purpose: the
    first version of this test only asserted the string 'mkdtemp' appeared
    somewhere, which a mutation that swapped the call for a fixed path
    survived — the word was still there, in the comment explaining why the
    mutation is wrong.
    """
    s = _src()
    code = re.sub(r'//.*', '', s)          # strip line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)   # and block comments
    assert re.search(r'\bmkdtempSync\s*\(', code), (
        'the scratch dir must be created by mkdtempSync; a fixed name lets two '
        'concurrent renders share one directory and one of them cleans up the '
        "other's bundle mid-render"
    )


def test_the_scratch_directory_is_removed_and_not_merely_moved():
    """The half that "just point outDir at E:" gets wrong.

    prepareOutDir never deletes, so an outDir without an explicit rm leaks
    exactly as much as before — on a different drive.
    """
    s = _code()
    assert re.search(r'\.rmSync\s*\(', s), (
        'nothing removes the bundle directory; passing outDir only relocates '
        'the leak rather than ending it'
    )
    assert re.search(r'force:\s*true', s), (
        'cleanup must tolerate the directory already being gone, or a '
        'double-cleanup turns a successful render into a thrown error'
    )


def test_cleanup_covers_the_failure_path():
    """A render that throws after bundling is the common case, not the rare one.

    Missing props, a bad composition id, an encoder failure — all of them leave
    the bundle behind unless cleanup is on a path a throw actually unwinds.
    """
    s = _code()
    assert 'finally' in s, (
        'cleanup must be in a finally: the failure modes that matter all '
        'happen AFTER bundling, which is the expensive step'
    )


def test_an_interrupted_render_is_still_cleaned_up():
    """Ctrl-C skips finally. A 20-minute render abandoned at frame 900 would
    otherwise leave its 800 MB behind, which is when someone is least likely to
    go looking for it."""
    s = _code()
    assert 'SIGINT' in s and 'SIGTERM' in s, (
        'a cancelled render must clean up too — otherwise the exact moment a '
        'user aborts a long render is the moment the disk fills'
    )


def test_the_scratch_lives_where_git_ignores_it():
    """Not a correctness rule — a hygiene one.

    The scratch is ~800 MB of generated output. If it ever lands somewhere git
    does not ignore, someone eventually commits it.
    """
    s = _code()
    assert '.remotion' in s, 'the scratch directory should be under .remotion/'
    ignored = (ROOT / '.gitignore').read_text(encoding='utf-8')
    # The scratch lives at studio/.remotion/, so the rule that covers it is the
    # prefixed one; the bare /.remotion/ entry covers a different path and does
    # not make this assertion true.
    assert re.search(r'^studio/\.remotion/$', ignored, re.M), (
        'studio/.remotion/ is not gitignored — an 800 MB generated directory '
        'would be one `git add .` away from the repository'
    )


def test_the_bundler_never_cleans_up_after_itself():
    """Pins the upstream fact this whole file rests on.

    If a future Remotion release starts deleting its own temp bundle, this
    assertion fails and the honest response is to delete the workaround, not to
    make the test pass. Every comment in render.mjs cites this behaviour, so it
    must not be allowed to change silently underneath them.
    """
    bundler = ROOT / 'studio' / 'node_modules' / '@remotion' / 'bundler' / 'dist' / 'bundle.js'
    if not bundler.exists():
        import pytest
        pytest.skip('node_modules not installed — upstream behaviour unpinned')
    js = bundler.read_text(encoding='utf-8', errors='replace')
    assert 'remotion-webpack-bundle-' in js, (
        'the bundler no longer mkdtemps under that prefix — re-verify whether '
        'it now cleans up after itself before trusting the workaround'
    )
    prepare = js.split('prepareOutDir = async', 1)[-1].split('};', 1)[0]
    assert 'rmSync' not in prepare and 'rm(' not in prepare, (
        'prepareOutDir now removes the directory it creates — the workaround in '
        'render.mjs has become redundant and should be dropped, not layered on'
    )
