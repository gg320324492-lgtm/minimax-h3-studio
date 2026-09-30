"""Single source of truth for locating the ffmpeg/ffprobe binaries.

WHY THIS EXISTS
---------------
On this machine `ffmpeg` on PATH is **not** a normal install. It resolves to
the binary bundled with GNU Octave:

    E:\\MATLAB\\Octave\\Octave-11.3.0\\mingw64\\bin\\ffmpeg.exe   -> 4.2.11

Meanwhile a full 7.1.1 build sits unused in the repo at
`tools/ffmpeg-7.1.1-full_build/bin/`.  That makes the whole pipeline depend on
a third-party application being installed and on PATH -- uninstalling or
upgrading Octave silently changes (or breaks) every encode, and version-gated
options such as `-fps_mode` (ffmpeg >= 5.0) fail with
`Unrecognized option 'fps_mode'` only on the old binary.

USAGE
-----
Prefer the explicit constants:

    from ffmpeg_env import FFMPEG, FFPROBE
    subprocess.run([FFMPEG, '-y', '-i', src, ...], check=True)

If you cannot edit the call sites (legacy scripts that hardcode the string
`'ffmpeg'`), call `prepend_to_path()` instead -- it prepends the resolved
binary's directory to PATH *for this process and its children only*, so
existing `['ffmpeg', ...]` argument lists pick up the intended build with no
other change.

NOTE ON COMPATIBILITY
---------------------
Switching builds can change encoder output. The EP01 delivery chain was
produced with 4.2.11; do not silently repoint a shipped pipeline at 7.1.1
without re-verifying its output. `report()` prints what is actually resolved so
the choice is always visible in logs.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
_BUNDLED_BIN = REPO / 'tools' / 'ffmpeg-7.1.1-full_build' / 'bin'


def _resolve_dir() -> tuple[Path | None, str]:
    """Decide which directory wins, and why.

    MINIMAX_FFMPEG_DIR=<dir>   use this directory (highest priority)
    MINIMAX_FFMPEG_LEGACY=1    use PATH only -- i.e. whatever the machine has,
                               which on this box is Octave's bundled 4.2.11.
                               Set this when you need byte-comparable output
                               with artefacts produced before 2026-09-19.
    default                    the repo-bundled 7.1.1 build
    """
    env_dir = os.environ.get('MINIMAX_FFMPEG_DIR')
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir), 'MINIMAX_FFMPEG_DIR'
    if os.environ.get('MINIMAX_FFMPEG_LEGACY', '').strip() in ('1', 'true', 'yes'):
        return None, 'MINIMAX_FFMPEG_LEGACY (PATH)'
    if (_BUNDLED_BIN / 'ffmpeg.exe').exists() or (_BUNDLED_BIN / 'ffmpeg').exists():
        return _BUNDLED_BIN, 'repo-bundled'
    return None, 'PATH (bundled build not found)'


_DIR, _DIR_SOURCE = _resolve_dir()


def _pick(name: str) -> tuple[str, str]:
    """Return (path, provenance)."""
    if _DIR is None:
        return name, _DIR_SOURCE
    for cand in (_DIR / f'{name}.exe', _DIR / name):
        if cand.exists():
            return str(cand), _DIR_SOURCE
    return name, 'PATH (not found in ' + str(_DIR) + ')'


FFMPEG, FFMPEG_SOURCE = _pick('ffmpeg')
FFPROBE, FFPROBE_SOURCE = _pick('ffprobe')

_VERSION_RE = re.compile(r'version\s+(\S+)')


def version(binary: str = FFMPEG) -> str:
    """Return the reported version string, or '?' if it cannot be determined."""
    try:
        r = subprocess.run([binary, '-version'], capture_output=True, timeout=20)
        head = r.stdout.decode('utf-8', 'replace').splitlines()[0]
        m = _VERSION_RE.search(head)
        return m.group(1) if m else head.strip()
    except Exception:
        return '?'


def prepend_to_path(binary: str = FFMPEG, quiet: bool = False) -> None:
    """Put the resolved binary's directory first on PATH (this process only).

    This is the low-risk way to fix a legacy script that hardcodes the string
    `'ffmpeg'` in its argument lists: one import line, no call-site edits.

    Prints a one-line notice to stderr whenever the resolved directory differs
    from what PATH would have given, so a version change is never silent.

    BUGFIX (P0 audit R4): a bare command name ('ffmpeg', i.e. the bundled build
    was not found) used to go through abspath() and resolve to CWD/ffmpeg —
    whose parent is CWD, a directory that always exists — so the CWD got
    prepended to PATH. A bare name now returns without touching PATH; if the
    bundled build is missing that is a loud, correct failure, not a silent
    PATH poisoning.
    """
    if not os.path.dirname(binary):  # bare command name, not a path
        if not quiet:
            print(f'[ffmpeg_env] WARNING: no bundled ffmpeg found; leaving PATH '
                  f'alone. Bare "{binary}" will resolve via PATH — which on this '
                  f'machine is GNU Octave\'s 4.2.11, not a supported build. '
                  f'Populate tools/ or set H3_FFMPEG_DIR.',
                  file=sys.stderr)
        return
    d = os.path.dirname(os.path.abspath(binary))
    if not d or not os.path.isdir(d):
        return
    parts = os.environ.get('PATH', '').split(os.pathsep)
    already_first = bool(parts) and os.path.normcase(parts[0]) == os.path.normcase(d)
    if not already_first and not quiet:
        print(f'[ffmpeg_env] using {binary} ({version(binary)}) [{FFMPEG_SOURCE}]',
              file=sys.stderr)
    if already_first:
        return
    os.environ['PATH'] = os.pathsep.join([d] + [p for p in parts
                                                if os.path.normcase(p) != os.path.normcase(d)])


def report(stream=sys.stdout) -> None:
    """Print resolved binaries, provenance and versions. Call this at startup."""
    for name, path, src in (('ffmpeg', FFMPEG, FFMPEG_SOURCE),
                            ('ffprobe', FFPROBE, FFPROBE_SOURCE)):
        print(f'{name:8} {version(path):<28} [{src}] {path}', file=stream)


if __name__ == '__main__':
    report()
