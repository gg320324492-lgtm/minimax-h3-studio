"""Regenerate problem shots S03C and S05A with stronger prompts.

S03C: Pendant light crash aftermath - need to see actual broken pieces
S05A: Coffee cup close-up - need to see only the cup, no people
"""
import json
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')
PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, method='GET', data=None):
    url = f'{SERVER}{path}'
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))


def workflow_to_prompt(workflow, custom_prompt, ref_images, custom_seed, custom_length, width, height):
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
        if nid == '138':
            inputs['value'] = custom_prompt
        if nid in ('137', '139') and ref_images:
            slot = '0' if nid == '137' else '1'
            if slot in ref_images:
                inputs['image'] = ref_images[slot]
        if nid == '136':
            inputs['length'] = custom_length
            inputs['noise_seed'] = custom_seed
            inputs['prompt'] = custom_prompt
            inputs['width'] = width
            inputs['height'] = height
        if nid == '132':
            inputs['value'] = custom_length / 24.0
        for inp in (n.get('inputs') or []):
            lid = inp.get('link'); name = inp.get('name')
            if lid is None or name is None:
                continue
            if name in inputs:
                continue
            if lid in link_map:
                src_id, src_slot = link_map[lid]
                inputs[name] = [str(src_id), src_slot]
        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt


def find_latest_video():
    out_dir = Path(r'E:\ComfyUI\output')
    files = list(out_dir.glob('MiniMax_H3*.mp4'))
    if not files:
        files = list(out_dir.rglob('*.mp4'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


# S03C variants - emphasize BROKEN, SHATTERED, FALLEN state
S03C_VARIANTS = [
    # Variant 1: Heavy broken state
    """Use <Picture 3> as the executive office.

EXTREME CLOSE-UP of the dark wood executive desk surface. The large circular pendant light has CRASHED DOWN onto the desk and floor.

The light fixture is now BROKEN IN PIECES on the desk:
- The circular metal frame is twisted and bent
- Glass pieces are shattered and scattered EVERYWHERE on the desk
- The mounting rod has snapped and lies across the desk
- Crystal/glass shards are visible catching light

The desk surface is covered with debris - glass fragments, metal pieces, dust, and small particles floating in the air.

Dramatic aftermath scene. Strong directional lighting catches the broken glass.

NO PEOPLE in the scene. Focus entirely on the destroyed light fixture and debris.

Cinematic, photorealistic, premium Chinese executive office aesthetic.
9:16 vertical composition.""",
    # Variant 2: Aftermath from a wider angle
    """Use <Picture 3> as the executive office.

WIDE SHOT of the premium Chinese executive office AFTER the pendant light has crashed.

On the dark wood executive desk surface and the floor around it:
- BROKEN GLASS shards scattered everywhere
- BENT METAL pieces of the circular pendant light frame
- The crystal rings of the light are shattered
- Small dust particles still floating in the air from the impact

The ceiling above shows the empty MOUNTING POINT where the light used to hang - now broken and dangling wires visible.

Strong cinematic lighting emphasizing the destruction. NO PEOPLE in the scene.

Photorealistic, premium executive office aesthetic, dramatic aftermath.
9:16 vertical composition.""",
    # Variant 3: Floor-level aftermath
    """Use <Picture 3> as the executive office.

LOW ANGLE SHOT looking down at the floor of the premium executive office.

The CRASHED pendant light lies broken on the marble floor:
- Metal frame twisted into unrecognizable shape
- Crystal/glass pieces shattered and scattered
- Mounting rod snapped
- Small glass fragments sparkling on the polished floor surface

Looking up, you can see the BROKEN CEILING MOUNT with dangling wires where the light used to be attached.

Debris field on the floor. No people visible. Dramatic aftermath moment.

Cinematic, photorealistic, premium Chinese executive office.
9:16 vertical composition.""",
]

# S05A variants - emphasize CLOSE-UP of COFFEE CUP, NO PEOPLE
S05A_VARIANTS = [
    # Variant 1: Direct close-up of cup on desk
    """Use <Picture 3> as the executive office.

EXTREME CLOSE-UP still life shot. A single white porcelain coffee cup sits on the dark wood executive desk surface.

The cup is white ceramic with subtle elegant shape. Inside is dark brown coffee liquid, perfectly still, no ripples. The cup is positioned in the center of the frame.

Soft natural daylight from the office windows creates gentle reflections on the cup surface and the polished desk.

NO PEOPLE visible anywhere. NO HANDS holding the cup. NO body parts in frame.

Background is the office desk surface - dark wood with subtle grain. Soft shallow depth of field, bokeh effect on background.

Cinematic, photorealistic, premium product photography style.
9:16 vertical composition. The single coffee cup is the only subject.""",
    # Variant 2: Coffee cup with subtle office background
    """Use <Picture 3> as the executive office.

INTIMATE STILL LIFE close-up of a single white ceramic coffee cup with brown coffee inside, sitting alone on a dark wood executive desk.

The cup is the ONLY subject in the frame. No hands, no arms, no body parts.

Composition: cup slightly off-center following rule of thirds. Camera at table level looking down at the cup at a slight angle.

Background: soft focus showing executive office elements (window light, perhaps edge of leather chair) - all heavily blurred so the cup remains the focus.

Subtle steam wisps could rise from the coffee for atmosphere.

Photorealistic, premium commercial photography aesthetic.
9:16 vertical composition.""",
    # Variant 3: From above
    """Use <Picture 3> as the executive office.

OVERHEAD SHOT looking straight down at a single white porcelain coffee cup on dark wood desk surface.

The cup is centered in frame, with rich dark brown coffee visible inside.

The dark wood grain of the desk surface is clearly visible around the cup.

NO PEOPLE. NO HANDS. NO BODY. Just the cup on the desk from directly above.

Soft shadows indicate natural light. The cup appears small in the wide frame, isolated on the desk.

Cinematic, photorealistic, minimalist product photography.
9:16 vertical composition.""",
]


def gen_shot(shot_id, variant_idx, prompt, length_frames, seed):
    log(f'  GEN: {shot_id}_v{variant_idx+1} (length={length_frames})')
    log(f'    prompt: {prompt[:120]}')

    shot_dir = PROJECT / f'03_video_raw/{shot_id}'
    shot_dir.mkdir(parents=True, exist_ok=True)
    slug = f'{shot_id}_v{variant_idx+1}'
    dst = shot_dir / f'{slug}.mp4'
    if dst.exists() and dst.stat().st_size > 100000:
        log(f'    SKIP: {dst.name} exists')
        return dst

    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    api_prompt = workflow_to_prompt(
        wf, prompt,
        {'0': 'OFFICE_MASTER_REFERENCE.png', '1': 'CEO_MASTER_REFERENCE.png'},
        custom_seed=seed,
        custom_length=length_frames,
        width=768, height=1344
    )
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    if 'error' in resp:
        log(f'  ERROR: {resp["error"]["type"]}: {resp["error"]["message"]}')
        return None
    pid = resp.get('prompt_id')
    log(f'    pid={pid}')
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            if rec.get('status', {}).get('completed') or 'outputs' in rec:
                wall = time.time() - t0
                log(f'    DONE in {wall:.1f}s')
                break
            st = rec.get('status', {}).get('status_str')
            if st in ('error', 'failed'):
                log(f'    FAILED: {st}')
                return None
        time.sleep(5)
    time.sleep(3)
    src = find_latest_video()
    if not src:
        return None
    shutil.copy2(str(src), str(dst))
    log(f'    saved: {dst}')
    return dst


def main():
    log('=== Regenerating problem shots ===')

    # S03C: 3 variants of crash aftermath (longer length for more visible content)
    log('\n--- S03C: Pendant light crash aftermath ---')
    for i, prompt in enumerate(S03C_VARIANTS):
        gen_shot(
            shot_id='S03C',
            variant_idx=i,
            prompt=prompt,
            length_frames=39,  # 1.6s each
            seed=3202 + i * 1000
        )

    # S05A: 3 variants of coffee cup close-up (varying seeds for diversity)
    log('\n--- S05A: Coffee cup close-up ---')
    for i, prompt in enumerate(S05A_VARIANTS):
        gen_shot(
            shot_id='S05A',
            variant_idx=i,
            prompt=prompt,
            length_frames=22,  # 0.9s each
            seed=5002 + i * 1000
        )

    log('\n=== Regeneration complete ===')
    log(f'Inspect generated variants: 03_video_raw/S03C/ and 03_video_raw/S05A/')


if __name__ == '__main__':
    main()