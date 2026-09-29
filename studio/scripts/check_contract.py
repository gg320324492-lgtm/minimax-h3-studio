"""Contract sync self-check (Phase 6.7).

1. Re-export zod schemas and verify the committed .schema.json files match (drift = fail).
2. Validate every public/jobs/*/props.json against its matching schema (smoke).

Run from anywhere:  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/check_contract.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
VENV_PY = r'E:\ComfyUI\venv\Scripts\python.exe'

failures = 0


def fail(msg: str) -> None:
    global failures
    failures += 1
    print(f'[FAIL] {msg}')


def main() -> int:
    # 1. schema freshness
    import shutil
    pnpm = shutil.which('pnpm')
    if not pnpm:
        fail('pnpm not on PATH')
    else:
        r = subprocess.run([pnpm, 'exec', 'tsx', 'bin/export-schema.ts'],
                           cwd=STUDIO, capture_output=True, text=True)
        if r.returncode:
            fail(f'schema export errored: {r.stderr[-400:]}')
    for name in ('timeline-v2.schema.json', 'report-data.schema.json'):
        p = STUDIO / 'src' / 'schemas' / name
        diff = subprocess.run(['git', 'diff', '--exit-code', '--', f'studio/src/schemas/{name}'],
                              cwd=STUDIO.parent, capture_output=True, text=True)
        if diff.returncode:
            fail(f'{name} drifted from committed version — review and commit the new export')
        else:
            print(f'[OK] {name} in sync')

    # 2. props smoke validation（按内容路由到对应契约，而不是按文件名猜）
    import jsonschema
    tl_schema = json.loads((STUDIO / 'src' / 'schemas' / 'timeline-v2.schema.json').read_text(encoding='utf-8'))
    rp_schema = json.loads((STUDIO / 'src' / 'schemas' / 'report-data.schema.json').read_text(encoding='utf-8'))
    for props_file in sorted((STUDIO / 'public' / 'jobs').rglob('*.json')):
        if props_file.name in ('pump_envelope.json', 'cover_bg.json') or props_file.suffix != '.json':
            continue
        try:
            data = json.loads(props_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue  # 非 JSON 内容的杂项文件跳过
        if not isinstance(data, dict) or 'version' not in data:
            continue
        schema = rp_schema if data.get('template') == 'report-vertical' else tl_schema
        try:
            jsonschema.validate(data, schema)
            print(f'[OK] {props_file.relative_to(STUDIO)}')
        except jsonschema.ValidationError as e:
            fail(f'{props_file.relative_to(STUDIO)}: {e.message[:120]}')

    print(f'\nresult: {"PASS" if failures == 0 else f"FAIL ({failures})"}')
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
