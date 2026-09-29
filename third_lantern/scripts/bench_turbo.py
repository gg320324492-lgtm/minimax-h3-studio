"""Turbo A/B: regenerate S13 with the 768p 8-step turbo LoRA (shift 6) using
the same structured prompt + same KF guides as the full-quality S13, for
direct speed/quality comparison against 03_video_raw_upgrade/S13.
"""
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, r'E:/Minimax-H3/third_lantern/scripts')
import upgrade_performance as up

SERVER = 'http://127.0.0.1:8188'
COMFY_INPUT = Path(r'E:/ComfyUI/input')
COMFY_OUTPUT = Path(r'E:/ComfyUI/output')
BENCH = up.PROJECT / '10_benchmark'
LORA768 = 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'

up.STEPS = 8
up.log('turbo mode: 8 steps, 768p LoRA, shift 6')


def api(path, data=None, timeout=14400):
    req = urllib.request.Request(
        f'{SERVER}{path}',
        data=json.dumps(data).encode() if data is not None else None,
        method='POST' if data is not None else 'GET',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def turbofy(graph):
    """Swap in the 768p turbo LoRA + shift 6 on the flattened r2v graph."""
    lora_id = None
    for nid, nd in graph.items():
        if nd['class_type'] == 'LoraLoaderModelOnly':
            lora_id = nid
            nd['inputs']['lora_name'] = LORA768
            nd['inputs']['strength_model'] = 1.0
    if lora_id is None:
        raise RuntimeError('no LoraLoaderModelOnly node in r2v graph')
    graph[str(700)] = {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {
        'model': [lora_id, 0], 'shift_video': 6.0, 'shift_audio': 3.0}}
    graph['124']['inputs']['model'] = ['700', 0]
    graph['126']['inputs']['model'] = ['700', 0]
    return graph


def submit_and_wait(graph, tag):
    resp = api('/prompt', {'prompt': graph})
    if 'prompt_id' not in resp:
        raise RuntimeError(f'submit error: {json.dumps(resp)[:1200]}')
    pid = resp['prompt_id']
    up.log(f'{tag}: submitted {pid}')
    t0 = time.time()
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                raise RuntimeError(f'FAILED: {str(st.get("messages"))[-800:]}')
            if st.get('completed') or 'outputs' in rec:
                break
        time.sleep(5)
    found = []
    for node_out in (rec.get('outputs') or {}).values():
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(COMFY_OUTPUT / sub / item['filename'])
    src = next((c for c in found if c.exists()), None)
    if src is None:
        raise RuntimeError(f'{tag}: no output')
    up.log(f'{tag}: done in {(time.time()-t0)/60:.1f} min')
    return src


def main():
    BENCH.mkdir(parents=True, exist_ok=True)
    spec = up.SHOTS['S13']
    length = spec['len']
    duration = length / up.FPS
    prompt = up.shot_prompt(spec['subject3'], spec['kf_defs'], spec['pic_retention'],
                            duration, spec['desc'], spec['sounds'])
    refs = []
    for r in spec['refs']:
        name = f'lz3_{r}'
        src = COMFY_INPUT / name
        if not src.exists():
            shutil.copy2(up.PROJECT / '00_art' / r, src)
        refs.append(name)

    # reuse the existing full-run KFs as guides (same anchors as full S13)
    guides = []
    for fidx in spec['kf_frames']:
        gname = f'lz3_bench_S13_KF{fidx}.png'
        src = BENCH / f'KF_f{fidx:03d}.png'
        # S13 anchors: use the full run's extracted KFs for identical anchors
        alt = up.PROJECT / '03_video_raw_upgrade' / 'S13' / f'S13_KF_f{fidx:03d}.png'
        pick = alt if alt.exists() else src
        shutil.copy2(pick, COMFY_INPUT / gname)
        guides.append((gname, fidx))

    graph = turbofy(up.build_graph(prompt, spec['seed'] + 900, length, refs,
                                   guides, 'lz3_turbo_S13'))
    src = submit_and_wait(graph, 'turbo_S13')
    dst = BENCH / 'turbo_S13.mp4'
    shutil.copy2(src, dst)
    print(f'saved -> {dst}')


if __name__ == '__main__':
    main()
