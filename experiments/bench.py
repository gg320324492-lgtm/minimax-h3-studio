"""Benchmark ComfyUI T2V/R2V inference via HTTP API.

Handles:
- Filter MarkdownNote and other non-executable doc nodes
- Convert workflow JSON nodes[] -> prompt API format
- For each node, use widgets_values_named as inputs (handles subgraph case
  where link IDs refer to internal nodes; widget values are already filled)
- For top-level links, resolve them normally

Usage: python bench.py <workflow.json> --label "name" [--seed N]
"""
import json
import sys
import time
import urllib.request
import urllib.error
import argparse
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'

# Non-executable (visual/documentation) nodes to strip
SKIP_TYPES = {
    'MarkdownNote', 'Note',
    'Reroute',
    # Subgraph UUIDs (expanded internally — but include if API supports them)
}


def api(path, method='GET', data=None):
    url = f'{SERVER}{path}'
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode('utf-8', errors='replace')
        print(f'[bench] HTTP {e.code}: {body_text[:800]}')
        raise


def workflow_to_prompt(workflow):
    """Convert UI workflow -> API prompt format.

    Strategy:
      - Skip non-executable doc nodes
      - For each remaining node:
          - Start with widgets_values_named as inputs
          - Overlay positional widgets_values (in widgets_names order, if available)
          - For inputs[] with link refs to TOP-LEVEL links, resolve to [src_id, slot]
          - For inputs[] with link refs to subgraph-internal links, ignore (the
            widget values from widgets_values_named already cover them)
    """
    nodes = workflow.get('nodes', [])
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}  # link_id -> (src_id, slot)

    prompt = {}
    skipped = []
    for n in nodes:
        if n.get('type') in SKIP_TYPES:
            skipped.append((n['id'], n['type']))
            continue

        # Skip pure subgraph-wrapper nodes (UUID type) — their inner graph
        # is what actually runs, and the subgraph's own inputs are exposed
        # via widgets_values. We pass them through.
        nid = str(n['id'])
        inputs = {}

        # 1) Named widget values take precedence (handles subgraph case)
        named = n.get('widgets_values_named') or {}
        for k, v in named.items():
            inputs[k] = v

        # 2) Positional widget values (in widgets_names order) fill any gaps
        names = n.get('widgets_names') or []
        values = n.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]

        # 3) Link inputs from top-level links
        for inp in (n.get('inputs') or []):
            link_id = inp.get('link')
            name = inp.get('name')
            if link_id is None or name is None:
                continue
            if link_id in link_map:
                src_id, src_slot = link_map[link_id]
                inputs[name] = [str(src_id), src_slot]
            # else: internal subgraph link, ignore (already in named)

        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}

    return prompt, skipped


def queue_prompt(prompt):
    return api('/prompt', method='POST', data={'prompt': prompt})


def get_history(prompt_id):
    return api(f'/history/{prompt_id}')


def wait_for_completion(prompt_id, poll=2.0, timeout=1800):
    t0 = time.time()
    while True:
        h = get_history(prompt_id)
        if prompt_id in h:
            rec = h[prompt_id]
            status = rec.get('status', {})
            if status.get('completed') or 'outputs' in rec:
                return status, time.time() - t0, rec
            if status.get('status_str') in ('error', 'failed'):
                return status, time.time() - t0, rec
        if time.time() - t0 > timeout:
            return {'status_str': 'timeout'}, time.time() - t0, {}
        time.sleep(poll)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('workflow', type=Path)
    ap.add_argument('--label', default='run')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    print(f'[bench] Loading workflow: {args.workflow}')
    wf = json.loads(args.workflow.read_text(encoding='utf-8'))

    prompt, skipped = workflow_to_prompt(wf)
    print(f'[bench] Converted: {len(prompt)} API nodes (skipped {len(skipped)} doc nodes)')
    if skipped:
        print(f'[bench]   skipped: {skipped[:5]}{"..." if len(skipped)>5 else ""}')

    print(f'[bench] Submitting to {SERVER}/prompt ...')
    t_submit = time.time()
    try:
        resp = queue_prompt(prompt)
    except urllib.error.HTTPError as e:
        print(f'[bench] submit FAILED: {e.code}')
        return 1
    pid = resp.get('prompt_id')
    if not pid:
        print(f'[bench] submit ERROR: {resp}')
        return 1
    print(f'[bench] prompt_id = {pid}')

    print(f'[bench] Waiting for completion (label={args.label})...')
    status, elapsed, rec = wait_for_completion(pid)
    wall = time.time() - t_submit
    status_str = status.get('status_str', '?')

    print(f'\n========== [{args.label}] ==========')
    print(f'  status:    {status_str}')
    print(f'  exec time: {elapsed:.2f} s')
    print(f'  wall time: {wall:.2f} s')
    if rec.get('outputs'):
        files = []
        for nid, out in rec['outputs'].items():
            for v in (out.get('videos') or []):
                files.append(v.get('filename'))
            for img in (out.get('images') or []):
                files.append(img.get('filename'))
        print(f'  outputs:   {files}')
    if status_str in ('error', 'failed'):
        msgs = rec.get('status', {}).get('messages', [])
        for m in msgs[-3:]:
            print(f'  msg:       {m}')
    print('====================================\n')

    return 0 if status_str == 'success' else 1


if __name__ == '__main__':
    sys.exit(main())
