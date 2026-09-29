"""Generate Lulu 15-second short animation, then upscale to 2K and 4K."""
import json
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')
OUTPUT_DIR = Path(r'E:\ComfyUI\output\video')
COMFY_OUTPUT = Path(r'E:\ComfyUI\output')  # history subfolders are relative to this root
DESKTOP_DIR = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs')
LOG = Path(r'E:\Minimax-H3\lulu_gen.log')

# 15 second animation, 24fps -> 362 frames (17*21+5 frame grid)
LENGTH_FRAMES = 362

PROMPT = """Pixar-quality 3D animated short film, soft volumetric lighting, golden hour, Studio Ghibli color palette, gentle depth of field, cute mascot character design.
Character: Lulu (噜噜),, a round fluffy cream-white creature with huge sparkly eyes, tiny pink nose, soft plush fur, 30cm tall, like a baby chickadee mixed with a Ghibli totoro.

[Shot 1] 0s-4s: Wide establishing shot of a sunlit meadow at golden hour. Camera slowly pushes in from low angle. Lulu is curled asleep next to a large daisy flower, breathing softly, fur ruffled by gentle breeze. Tiny dust motes and flower petals drift through warm volumetric light shafts. Peaceful ambience, soft wind, distant birdsong.

[Shot 2] 4s-8s: Cut to extreme close-up of Lulu face, eyes closed. A tiny iridescent blue butterfly gently lands on Lulu pink nose. Pause for 1s. Then Lulu sneezes adorably (ah-choo!), nose scrunches, eyes pop open wide in surprise, butterfly flutters away. Camera stays close on cute reaction. Sneeze sound, butterfly wing flutter, surprised gasp.

[Shot 3] 8s-12s: Wide tracking shot. Lulu hops after the butterfly through the meadow grass, bouncing playfully with each hop, fur bouncing with movement. Camera dollies alongside matching Lulu speed. Lulu leaps and nearly catches the butterfly mid-air, both tumbling gently, butterfly escaping. Soft giggling sound, hops landing on grass.

[Shot 4] 12s-15s: Cut to medium shot. Lulu finally catches the butterfly very gently in both paws, holds it up. The butterfly wings open slowly. Lulu and butterfly look at each other knowingly, both blink. Lulu smiles warmly, releases the butterfly gently, butterfly flies up into golden sunlight rays. Final frame: Lulu looking up at butterfly flying into sun.

Audio throughout: warm orchestral children's score, soft pizzicato strings, gentle flute melody, occasional chimes. Final chord resolves warmly.

Camera: each cut is a hard cut, no dissolves. Stable, smooth dollies only. Character motion: bouncy, exaggerated for cute effect, squishy fur.

No text, no subtitles, no logos, no watermarks. Family-friendly, magical, heartwarming tone throughout. Frame the final shot with butterfly in upper third golden light."""

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
    with urllib.request.urlopen(req, timeout=3600) as resp:
        return json.loads(resp.read().decode('utf-8'))

def workflow_to_prompt(workflow, custom_prompt, custom_seed, custom_length):
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
        if nid == '136':  # MiniMaxH3ReferenceToVideo
            inputs['length'] = custom_length
            inputs['noise_seed'] = custom_seed
            inputs['prompt'] = custom_prompt
        for inp in (n.get('inputs') or []):
            lid = inp.get('link'); name = inp.get('name')
            if lid is None or name is None: continue
            # Skip link override for fields we've already explicitly injected
            if name in inputs:
                continue
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

def gen_one(slug, prompt_text, base_seed, length):
    log(f'=== GEN: {slug} seed={base_seed} length={length} ===')
    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    for n in wf['nodes']:
        if n.get('type') == 'ResolutionSelector':
            n.setdefault('widgets_values_named', {})['megapixels'] = 0.98
    api_prompt = workflow_to_prompt(wf, prompt_text, base_seed, length)
    log(f'Submitting (1344x768, {length} frames = ~{length/24:.1f}s)...')
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
    # Resolve from THIS prompt's history record, not newest mtime: a concurrent
    # job finishing between our poll and our glob would otherwise make us copy
    # the wrong clip under our slug, with no error raised.
    src = None
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    for root_dir in (OUTPUT_DIR, COMFY_OUTPUT):
                        cand = root_dir / sub / item['filename']
                        if cand.exists():
                            src = cand
                            break
                    if src:
                        break
            if src:
                break
        if src:
            break
    if src is None:
        log('WARN: history carried no output path; falling back to newest-mtime')
        src = find_latest_mp4()
    if not src:
        log('No mp4 found!')
        return None, wall
    dst = DESKTOP_DIR / f'{slug}.mp4'
    shutil.copy2(str(src), str(dst))
    log(f'Copied to {dst}')
    return dst, wall

if __name__ == '__main__':
    slug = 'Lulu_15s_768p'
    path, wall = gen_one(slug, PROMPT, base_seed=88888, length=LENGTH_FRAMES)
    sz = f'{path.stat().st_size/1e6:.1f}MB' if path else '-'
    log(f'[{("OK" if path else "FAIL")}] {slug}: {wall:.1f}s, {sz}')