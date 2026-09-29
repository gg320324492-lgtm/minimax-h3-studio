"""Benchmark with file logging + N runs averaged."""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
LOG = Path(r'E:\MiniMax-H3\bench.log')

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line, flush=True)
    try:
        with LOG.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

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
        log(f'HTTP {e.code}: {body_text[:600]}')
        raise

def get_vram_mb():
    try:
        s = api('/system_stats')
        devs = s.get('devices', [])
        if devs:
            return round(devs[0].get('vram_free', 0) / 1024**2, 0)
    except Exception:
        pass
    return None

def workflow_to_prompt(workflow):
    nodes = workflow.get('nodes', [])
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    prompt = {}
    for n in nodes:
        if n.get('type') in SKIP:
            continue
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

def run_once(wf_path, seed, label):
    """Run a single benchmark; return (exit_code, wall_seconds)."""
    log(f'=== {label} seed={seed} ===')
    wf = json.loads(Path(wf_path).read_text(encoding='utf-8'))
    for n in wf['nodes']:
        if n.get('type') == 'MiniMaxH3ReferenceToVideo':
            n.setdefault('widgets_values_named', {})['noise_seed'] = seed
    prompt = workflow_to_prompt(wf)
    log(f'Converted: {len(prompt)} API nodes')

    t_submit = time.time()
    try:
        resp = api('/prompt', method='POST', data={'prompt': prompt})
    except urllib.error.HTTPError:
        log('submit FAILED')
        return 1, time.time() - t_submit
    pid = resp.get('prompt_id')
    log(f'prompt_id = {pid}')

    t0 = time.time()
    while True:
        try:
            h = api(f'/history/{pid}')
        except Exception as e:
            log(f'history poll err: {e}')
            time.sleep(2)
            continue
        if pid in h:
            rec = h[pid]
            status = rec.get('status', {})
            if status.get('completed') or 'outputs' in rec:
                wall = time.time() - t0
                files = []
                for nid, out in rec.get('outputs', {}).items():
                    for v in (out.get('videos') or []):
                        files.append(v.get('filename'))
                log(f'DONE in {wall:.1f}s; outputs={files}')
                return 0, wall
            if status.get('status_str') in ('error', 'failed'):
                wall = time.time() - t0
                log(f'ERROR after {wall:.1f}s')
                return 2, wall
        elapsed = time.time() - t0
        if elapsed > 900:
            log(f'TIMEOUT after {elapsed:.0f}s')
            return 3, elapsed
        if int(elapsed) % 20 == 0:
            vram = get_vram_mb()
            vram_str = f' VRAM free={vram}MB' if vram else ''
            log(f'  ...waiting {elapsed:.0f}s{vram_str}')
        time.sleep(2)

def main():
    if len(sys.argv) < 2:
        print('usage: bench_log.py <workflow.json> [seed] [label]')
        return 1
    wf_path = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7777
    label = sys.argv[3] if len(sys.argv) > 3 else 'run'

    code, wall = run_once(wf_path, seed, label)
    log(f'SUMMARY: {label} seed={seed} exit={code} wall={wall:.1f}s')
    return code

if __name__ == '__main__':
    sys.exit(main())