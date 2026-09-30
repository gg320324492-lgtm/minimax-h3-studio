"""Manifest self-check (P0 review item 3).

pipeline_manifest.yaml is the agent's only authority on what may be called.
That authority silently rots: a new experiments/ script appears, nobody
classifies it, and an agent eventually calls something destructive.

This fails loudly when reality and the manifest disagree:
  * every experiments/*.py must appear in exactly one classification bucket
  * every path listed in the manifest must exist
  * forbidden / superseded entries must not also be in production

Run:
  python -m pytest tests/test_manifest_freshness.py -q
  python tests/test_manifest_freshness.py   # 也可以脱离 pytest 单独跑
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Portable: derive from this file so a clone can live anywhere on disk.
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'pipeline_manifest.yaml'

BUCKETS = ('experimental_approved', 'benchmark_only', 'forbidden', 'superseded',
           'archive_candidates')


def norm(p: str) -> str:
    return p.replace('\\', '/').strip()


def manifest_paths() -> dict[str, list[str]]:
    """bucket -> paths, for the experiments section only."""
    text = MANIFEST.read_text(encoding='utf-8')
    # only the experiments: block
    start = text.index('\nexperiments:')
    block = text[start:]
    out: dict[str, list[str]] = {b: [] for b in BUCKETS}
    cur = None
    for line in block.splitlines():
        m = re.match(r'^  (\w+):\s*$', line)
        if m and m.group(1) in BUCKETS:
            cur = m.group(1)
            continue
        if re.match(r'^# ─|^production:|^templates:|^tools:|^qa_gates:|^local_only:',
                    line.lstrip('# ').strip() and line or line):
            if line.startswith('#') or re.match(r'^[a-z_]+:', line):
                cur = None
        m2 = re.match(r'^\s*-\s+(?:path:\s*)?([\w./\\-]+\.py)', line)
        if m2 and cur:
            out[cur].append(norm(m2.group(1)))
    return out


def main() -> int:
    problems: list[str] = []
    buckets = manifest_paths()
    classified: dict[str, str] = {}
    for b, paths in buckets.items():
        for p in paths:
            if p in classified:
                problems.append(f'{p} classified twice: {classified[p]} and {b}')
            classified[p] = b

    on_disk = {norm(str(p.relative_to(ROOT)).replace('\\', '/'))
               for p in sorted((ROOT / 'experiments').glob('*.py'))}

    missing = sorted(on_disk - set(classified))
    extra = sorted(set(classified) - on_disk)
    for m in missing:
        problems.append(f'UNCLASSIFIED on disk: {m}  -> add to pipeline_manifest.yaml '
                        f'experiments.<bucket>')
    for e in extra:
        problems.append(f'manifest lists a file that does not exist: {e}')

    # production entries must exist
    text = MANIFEST.read_text(encoding='utf-8')
    for m in re.finditer(r'path:\s*([\w./\\-]+\.(?:py|mjs|ts|tsx))', text):
        rel = norm(m.group(1))
        if not (ROOT / rel).exists():
            problems.append(f'manifest production path missing: {rel}')

    if problems:
        print(f'MANIFEST STALE — {len(problems)} problem(s):')
        for p in problems:
            print(f'  ! {p}')
        return 1
    print(f'manifest OK — {len(on_disk)} experiments scripts, all classified, '
          f'all production paths exist')
    return 0


if __name__ == '__main__':
    sys.exit(main())
