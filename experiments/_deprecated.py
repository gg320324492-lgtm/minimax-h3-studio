"""Deprecation banner for the superseded v1 upscale scripts.

Several legacy scripts (pipe_fast.py, pipe_4k_fast.py, pipe_4k.py,
upscale_x4v3.py, full_pipeline.py, upscale_to_4k.py, ...) contain defects that
were reproduced on this machine and fixed in `sr_pipeline_v2.py`. They are kept
for reference and for re-running historical comparisons, but running one by
accident silently degrades output, so each prints a warning.

The banner is emitted at *import* time via `warn()` rather than inside an
`if __name__ == '__main__':` guard, because most of these scripts parse
`sys.argv` and call `sys.exit(1)` at module level -- so their `main()` is dead
code and a guard-placed banner would never print.
"""
from __future__ import annotations

import sys

_PREFIX = 'DEPRECATED'


def warn(script: str, defects: list[str], usage: str,
         superseded_by: str = 'sr_pipeline_v2.py') -> None:
    lines = [
        f'{_PREFIX} -- {script} is superseded by {superseded_by}',
        '  Known defects in this script (all reproduced on this machine):',
        *[f'    * {d}' for d in defects],
        f'  Use:  {usage}',
    ]
    width = max(len(ln) for ln in lines) + 2
    bar = '=' * width
    out = [bar, *lines, bar]
    print('\n'.join(out), file=sys.stderr, flush=True)
