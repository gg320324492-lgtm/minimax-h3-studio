"""Stage a showcase graph for rendering, and prove the copy is not drifting.

Two graphs exist by design:
  * pipeline/examples/*.json        — the TRACKED source of truth
  * studio/public/jobs/<job>/*.json — the staging copy Remotion actually reads

The copy exists because Remotion Studio serves props over HTTP, so it has to
live under public/. That is the only reason it exists — and it is a liability:
being gitignored, it can drift from the source indefinitely and nobody notices
(a graph "edit" made only in the copy leaves no trace in any commit, which is
exactly what happened in P6.0).

So: CLI renders should point --props at the SOURCE. Staging is for Studio, and
this script is the only sanctioned way to produce a copy, and it writes a
sidecar fingerprint so drift is detectable.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/stage_showcase.py \
      --graph pipeline/examples/showcase_demo.json --job showcase_demo
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/stage_showcase.py --check --job showcase_demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
JOBS = ROOT / 'studio' / 'public' / 'jobs'
SIDECAR = '.staged-from.json'


def fingerprint(path: Path) -> str:
    """Hash of the graph's MEANINGFUL content.

    Key order and formatting are ignored on purpose: re-saving a file with
    different indentation must not look like a change.
    """
    doc = json.loads(path.read_text(encoding='utf-8'))
    payload = json.dumps(doc, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def stage(graph: Path, job: str, assets: list[str] | None = None) -> Path:
    graph = Path(graph).resolve()
    job_dir = JOBS / job
    job_dir.mkdir(parents=True, exist_ok=True)
    dst = job_dir / 'props.json'
    shutil.copy2(graph, dst)
    try:
        rel = graph.relative_to(ROOT).as_posix()
    except ValueError:  # a graph outside the repo — record it absolutely
        rel = graph.as_posix()
    (job_dir / SIDECAR).write_text(
        json.dumps({'source': rel,
                    'sha': fingerprint(graph),
                    'staged_at': __import__('datetime').date.today().isoformat()},
                   indent=2),
        encoding='utf-8')
    for extra in assets or []:
        src = ROOT / extra
        if src.exists():
            shutil.copy2(src, job_dir / src.name)
    return dst


def check(job: str) -> tuple[bool, str]:
    job_dir = JOBS / job
    sidecar = job_dir / SIDECAR
    if not sidecar.exists():
        return False, f'{job}: not staged (no {SIDECAR}) — run stage_showcase.py'
    meta = json.loads(sidecar.read_text(encoding='utf-8'))
    src = ROOT / meta['source']
    if not src.exists():
        return False, f'{job}: source graph {meta["source"]} is gone'
    now = fingerprint(src)
    staged = fingerprint(job_dir / 'props.json')
    if now != meta['sha']:
        return False, (f'{job}: SOURCE changed since staging '
                       f'({meta["sha"]} -> {now}) — re-stage or render with '
                       f'--props {meta["source"]}')
    if staged != now:
        return False, f'{job}: staged copy was edited by hand (drift) — re-stage'
    return True, f'{job}: staged copy matches {meta["source"]} ({now})'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', type=Path, help='source graph to stage')
    ap.add_argument('--job', required=True)
    ap.add_argument('--asset', action='append', default=[],
                    help='extra file (e.g. audio) to copy into the job dir')
    ap.add_argument('--check', action='store_true', help='verify instead of stage')
    args = ap.parse_args()

    if args.check:
        ok, msg = check(args.job)
        print(('[OK] ' if ok else '[DRIFT] ') + msg)
        return 0 if ok else 1

    if not args.graph:
        ap.error('--graph is required unless --check')
    dst = stage(args.graph, args.job, args.asset)
    print(f'staged {args.graph} -> {dst}')
    print(f'  fingerprint {fingerprint(args.graph)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
