"""Generate steampunk + deep sea at 768p, then upscale both to 2K."""
import json, shutil, sys, time, urllib.request, subprocess
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')
OUTPUT_DIR = Path(r'E:\ComfyUI\output\video')
DESKTOP_DIR = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs')
LOG = Path(r'E:\Minimax-H3\gen_remaining.log')

PROMPTS = [
    ('A3_steampunk_768p', 'Steampunk Victorian workshop interior, warm tungsten lighting, shallow depth of field, dust motes floating in light beams, brass and copper machinery everywhere, cinematic lens flares.\n\n[Shot 1] 0s-3s: Medium shot of an ornate brass automaton sitting on a workbench. Camera slowly dollies in. Gears visibly turning, small steam puffs releasing from miniature pistons.\n[Shot 2] 3s-5s: Cut to extreme close-up of the automaton clockwork heart - a spinning golden gear with ruby jewel at its center, light catching each rotation.\n\nAudio: Constant rhythmic tick-tock of clockwork, hissing steam releases, soft mechanical whirring, a single bell chime at 4s.\n\nNo text, no people. Object-focused cinematic.'),
    ('A4_deep_sea_768p', 'Cinematic underwater documentary style, shot on RED V-Raptor in IMAX, deep ocean bioluminescence, dark teal water with cyan and magenta glowing creatures, slow graceful motion.\n\n[Shot 1] 0s-2.5s: Slow drift through dark water. Tiny bioluminescent plankton particles drift past camera like underwater stars. A translucent jellyfish pulses in the background, cyan glow trailing its tentacles.\n[Shot 2] 2.5s-5s: Cut to a school of small glowing fish sweeping past camera in slow motion. Each fish leaves a faint magenta light trail. Camera follows them gently.\n\nAudio: Deep underwater ambience, low-frequency sonar-like pulse every 2 seconds, soft whale song humming in distance, gentle water movement whoosh as creatures pass.\n\nNo text, no people, no logos.'),
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
    files = sorted(OUTPUT_DIR.glob('MiniMax_H3_*.mp4'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def gen_one(slug, prompt_text, base_seed):
    log(f'=== GEN: {slug} seed={base_seed} ===')
    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    for n in wf['nodes']:
        if n.get('type') == 'ResolutionSelector':
            n.setdefault('widgets_values_named', {})['megapixels'] = 0.98
    api_prompt = workflow_to_prompt(wf, prompt_text, base_seed)
    log(f'Submitting (1344x768)...')
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    pid = resp['prompt_id']
    log(f'pid={pid}')
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
    src = find_latest_mp4()
    if not src:
        log('No mp4 found!')
        return None, wall
    dst = DESKTOP_DIR / f'{slug}.mp4'
    shutil.copy2(str(src), str(dst))
    log(f'Copied to {dst}')
    return dst, wall

def main():
    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    LOG.unlink(missing_ok=True)
    log('=== Generate remaining 768p ===')
    for i, (slug, prompt) in enumerate(PROMPTS):
        path, wall = gen_one(slug, prompt, base_seed=3000 + i * 999)
        sz = f'{path.stat().st_size/1e6:.1f}MB' if path else '-'
        log(f'[{("OK" if path else "FAIL")}] {slug}: {wall:.1f}s, {sz}')

if __name__ == '__main__':
    main()