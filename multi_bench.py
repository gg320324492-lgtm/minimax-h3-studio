"""Multi-run benchmark: run N times, print summary."""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
LOG = Path(r'E:\MiniMax-H3\bench_runs.log')

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')

def api(path, method='GET', data=None):
    url = f'{SERVER}{path}'
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode('utf-8'))

def workflow_to_prompt(workflow):
    nodes = workflow.get('nodes', [])
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    prompt = {}
    for n in nodes:
        if n.get('type') in SKIP: continue
        nid = str(n['id'])
        inputs = {}
        named = n.get('widgets_values_named') or {}
        inputs.update(named)
        names = n.get('widgets_names') or []
        values = n.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]
        for inp in (n.get('inputs') or []):
            lid = inp.get('link'); name = inp.get('name')
            if lid is None or name is None: continue
            if lid in link_map:
                inputs[name] = [str(link_map[lid][0]), link_map[lid][1]]
        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt

def run_once(wf_path, seed, run_idx):
    wf = json.loads(Path(wf_path).read_text(encoding='utf-8'))
    for n in wf['nodes']:
        if n.get('type') == 'MiniMaxH3ReferenceToVideo':
            n.setdefault('widgets_values_named', {})['noise_seed'] = seed
    prompt = workflow_to_prompt(wf)
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': prompt})
    pid = resp['prompt_id']
    log(f'  run#{run_idx} seed={seed} pid={pid} submitted')
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            if rec.get('status', {}).get('completed') or 'outputs' in rec:
                wall = time.time() - t0
                log(f'  run#{run_idx} DONE in {wall:.1f}s')
                return wall
            if rec.get('status', {}).get('status_str') in ('error', 'failed'):
                wall = time.time() - t0
                log(f'  run#{run_idx} ERROR in {wall:.1f}s')
                return -wall
        time.sleep(2)

def main():
    if len(sys.argv) < 4:
        print('usage: multi_bench.py <workflow.json> <n_runs> <label> [base_seed]')
        return 1
    wf_path = sys.argv[1]
    n_runs = int(sys.argv[2])
    label = sys.argv[3]
    base_seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1000

    log(f'===== START {label} (n={n_runs}, base_seed={base_seed}) =====')
    times = []
    for i in range(n_runs):
        wall = run_once(wf_path, base_seed + i*7, i+1)
        if wall > 0:
            times.append(wall)
        else:
            log(f'  run#{i+1} FAILED, skipping')
    log(f'===== END {label} =====')
    if times:
        avg = sum(times) / len(times)
        log(f'RESULT: {label} n={len(times)} avg={avg:.1f}s min={min(times):.1f}s max={max(times):.1f}s times={times}')
    return 0

if __name__ == '__main__':
    sys.exit(main())