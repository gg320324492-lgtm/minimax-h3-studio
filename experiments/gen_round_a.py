"""Round A: highest native 1344x768 (megapixels=0.98)."""
import json, shutil, sys, time, urllib.request
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')
OUTPUT_DIR = Path(r'E:\ComfyUI\output\video')
DESKTOP_DIR = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs')
LOG = Path(r'E:\Minimax-H3\gen_round.log')

PROMPTS = [
    ('A1_cyberpunk_768p', 'Cinematic cyberpunk style, neon-drenched Tokyo alley at midnight, heavy rain, shallow depth of field, anamorphic lens flares, wet reflective streets, steam rising from manholes.\n\n[Shot 1] 0s-3s: Slow dolly-in down a narrow alley. Walls of kanji signs flickering red and cyan. Rain pours in thick sheets, camera glides forward through puddles reflecting neon.\n[Shot 2] 3s-5s: Cut to close-up of a paper umbrella slowly spinning, water droplets falling in slow-motion, magenta light catching each drop, city sounds muffled behind.\n\nAudio: Persistent heavy rain ambience, distant traffic hum, a single saxophone note sustaining through Shot 2, faint muffled Japanese street chatter in Shot 1.\n\nNo text, no subtitles, no logos. Pure cinematic mood.'),
    ('A2_mountain_768p', 'Epic landscape cinematography, golden hour, shot on ARRI Alexa 65, anamorphic widescreen 2.39:1, IMAX-quality color grading. A lone hiker on a snow-covered mountain ridge at sunset.\n\n[Shot 1] 0s-2.5s: Wide aerial drone shot, slow forward push toward a silhouetted hiker standing on a ridge. Sun setting behind distant peaks, god-rays slicing through clouds, wind whipping snow off the ridge in waves.\n[Shot 2] 2.5s-5s: Cut to medium close-up of the hiker from behind, looking out at the valley below. Camera slowly pushes in. The hiker jacket ripples in the wind.\n\nAudio: Crisp cold wind gusting constantly, distant avalanche rumble at 3s, soft orchestral strings fading in at 2s building to a hopeful swell, complete silence at 5s.\n\nNo text, no logos, no people facing camera.'),
]

PROMPT_NODE_ID = '138'
SEED_NODE_ID = '136'

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

def workflow_to_prompt(workflow, custom_prompt, custom_seed):
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
        if nid == PROMPT_NODE_ID:
            inputs['value'] = custom_prompt
        if nid == SEED_NODE_ID:
            inputs['noise_seed'] = custom_seed
        for inp in (n.get('inputs') or []):
            lid = inp.get('link'); name = inp.get('name')
            if lid is None or name is None: continue
            if lid in link_map:
                src_id, src_slot = link_map[lid]
                if str(src_id) == PROMPT_NODE_ID and name == 'prompt':
                    inputs[name] = custom_prompt
                else:
                    inputs[name] = [str(src_id), src_slot]
        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt

def find_latest_mp4():
    """LAST-RESORT fallback only -- mtime guessing.

    Only reached when a prompt's /history record carries no output path. Prefer
    resolving from history; a concurrent job can make this pick the wrong file.
    """
    files = sorted(OUTPUT_DIR.glob('MiniMax_H3_*.mp4'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def find_latest_video(prefix='MiniMax_H3'):
    """REMOVED: mtime guessing picks the wrong clip under concurrency.

    Kept as a raising shim so any stale caller fails loudly instead of
    silently copying the wrong file. Use the /history outputs instead.
    """
    raise RuntimeError(
        'find_latest_video() is unsafe (mtime guessing). '
        'Resolve the artefact from the /history/<prompt_id> outputs instead.'
    )

def run_one(slug, prompt_text, base_seed, label='gen'):
    LOG.unlink(missing_ok=True)
    log(f'=== {label}: {slug} seed={base_seed} ===')
    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    # Find ResolutionSelector and bump megapixels to 0.98
    for n in wf['nodes']:
        if n.get('type') == 'ResolutionSelector':
            named = n.setdefault('widgets_values_named', {})
            named['megapixels'] = 0.98
    api_prompt = workflow_to_prompt(wf, prompt_text, base_seed)
    log('Submitting at megapixels=0.98 (1344x768)...')
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    pid = resp['prompt_id']
    log(f'prompt_id={pid}')
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            if rec.get('status', {}).get('completed') or 'outputs' in rec:
                wall = time.time() - t0
                log(f'DONE in {wall:.1f}s')
                break
            if rec.get('status', {}).get('status_str') in ('error', 'failed'):
                wall = time.time() - t0
                log(f'ERROR after {wall:.1f}s')
                return None, wall
        time.sleep(3)
    time.sleep(2)
    # Resolve the artefact from THIS prompt's history record, not by newest
    # mtime: a concurrent job can finish between our poll and our glob, and we
    # would then silently copy someone else's clip under our slug.
    src = None
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    cand = OUTPUT_DIR / (item.get('subfolder') or '') / item['filename']
                    if cand.exists():
                        src = cand
                        break
            if src:
                break
        if src:
            break
    if src is None:
        log('WARN: history carried no output path; falling back to newest-mtime')
        src = find_latest_mp4()
    if not src:
        log('No output mp4!')
        return None, wall
    dst = DESKTOP_DIR / f'{slug}.mp4'
    shutil.copy2(str(src), str(dst))
    log(f'Copied to {dst}')
    return dst, wall

def main():
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    LOG.unlink(missing_ok=True)
    log(f'=== ROUND A: native 768p (1344x768) ===')
    for i, (slug, prompt) in enumerate(PROMPTS):
        try:
            path, wall = run_one(slug, prompt, base_seed=1000 + i*777, label='A')
            sz = f'{path.stat().st_size/1e6:.1f}MB' if path else '-'
            log(f'[{("OK" if path else "FAIL")}] {slug}: {wall:.1f}s, {sz}')
        except Exception as e:
            log(f'EXCEPTION: {e}')

if __name__ == '__main__':
    main()