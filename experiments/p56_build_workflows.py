"""P56: build the six A/B comparison workflows for the Pika H3 Flex trial.

Sources:
  - the local r2v/t2v skeletons in E:\\Minimax-H3\\workflows (untouched)
  - the official Pika H3 Flex templates shipped inside E:\\ComfyUI
    (comfyui_workflow_templates_json), flattened with the P55 expand logic

Written to E:\\Minimax-H3\\workflows\\ (gitignored, like every workflow here):

  video_p56_r2v_A_turbo.json   local r2v skeleton, turbo LoRA on, 4 steps
  video_p56_r2v_B_flex.json    local r2v skeleton + pika ref2va LoRA, lcm,
                               ManualSigmas (7 values), 6 steps
  video_p56_fl2v_A_turbo.json  official fl2va template flattened, turbo_8step
                               LoRA, res_multistep + simple 8 steps
  video_p56_fl2v_B_flex.json   official fl2va template flattened, as shipped
  video_p56_t2v_A_full.json    local t2v skeleton, full 20 steps (as found)
  video_p56_t2v_B_flex.json    official pika t2v template flattened, as shipped

Control variables pinned across all six: seed 261662374822964, 1344x768
(0.98MP via ResolutionSelector where one exists, via 1344x768 reference
pictures where the template derives size from GetImageSize), 5 s -> 124 frames
(17k+5 grid), one shared prompt body, fp16 video VAE (the local production
choice — the official templates ship int8_convrot and are retargeted).

Each generated workflow is converted to an API prompt and spot-checked before
anything is allowed to run.
"""
import json
from pathlib import Path

from PIL import Image

from p56_runner import expand_subgraphs, flat_nodes_to_prompt, to_prompt

ROOT = Path(r'E:\Minimax-H3')
WF = ROOT / 'workflows'
TEMPLATES = Path(
    r'E:\ComfyUI\venv\Lib\site-packages\comfyui_workflow_templates_json'
    r'\templates')
COMFY_INPUT = Path(r'E:\ComfyUI\input')

SEED = 261662374822964
MP = 0.98
SIGMAS_STR = '1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0'
VIDEO_VAE = 'minimax_h3_video_vae_fp16.safetensors'
PIKA_REF2VA_LORA = 'pika_h3_flex_ref2va_v1_bf16.safetensors'
PIKA_FL2VA_LORA = 'pika_h3_flex_fl2va_v1_bf16.safetensors'
TURBO_REF_LORA = 'minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors'
TURBO_FL_LORA = 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'
FIRST_SRC = 'red_superboy_on_city_roof.png'
LAST_SRC = 'mecha_dragon_lightning.png'
FIRST_IMG = 'p56_ref_first_1344x768.png'
LAST_IMG = 'p56_ref_last_1344x768.png'

BODY = (
    'CUT 1: top-down view of the little boy superhero on the rooftop \u2014 '
    'red cape fluttering in the wind, hands planted on his hips, freckles and '
    'a cocky grin as he looks straight up into the camera. The camera slowly '
    'descends toward him as he delivers his line \u2014 as he speaks, '
    'comic-book graphic overlay text word by word in sync with his voice: '
    '"GET READY TO" - "MEET" \u2014 "YOUR" \u2014 "MAKER" \u2014 huge jagged '
    'comic lettering, white with heavy black outlines and red drop shadows, '
    'tilted at scrappy angles, until the three words hang stacked in the air '
    'above him between his face and the lens.\n'
    'TRANSITION: a violent WHIP PAN off the rooftop that SMEARS the floating '
    'words away with it, motion-streaked \u2014\n'
    'CUT 2: low hero angle on the colossal black mech-kaiju towering over the '
    'skyline as it rears back and unleashes a GIANT terrifying ROAR \u2014 '
    'jaws wide with fangs, red eyes and chest-core flaring blinding bright, a '
    "bold red countdown numeral 7 stamped in the top-left corner of the "
    'frame, blue lightning arcing off its head, the roar\'s shockwave '
    'rippling dust and rattling windows down the buildings, comic-style '
    'speed-lines and ink splatter bursting from the impact of the sound. It '
    'leans INTO the camera as the roar peaks. Hold on the roar.')

R2V_PROMPT = ('Bold comic-book ink style, heavy linework, red and blue-black '
              'palette, night city. Use <Picture 2> and <Picture 1> as '
              'reference frames.\n' + BODY)
T2V_PROMPT = ('Bold comic-book ink style, heavy linework, red and blue-black '
              'palette, night city.\n' + BODY)
FL2V_PROMPT = (
    'How the reference pictures align with the target video: Picture 1 (the '
    'little boy superhero on the rooftop) aligns with the 0.00-second mark of '
    'the target video; Picture 2 (the black mech-kaiju) aligns with the '
    '5.17-second mark of the target video.\n\n' + BODY)


def load(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


def save(workflow, path):
    Path(path).write_bytes(
        json.dumps(workflow, ensure_ascii=True, indent=1).encode('utf-8'))
    print(f'[build] wrote {Path(path).name}')


def node(wf, nid):
    return next(n for n in wf['nodes'] if n['id'] == nid)


def set_named(n, key, val):
    n.setdefault('widgets_values_named', {})[key] = val


def set_value(n, key, val):
    """Set a widget value across all three serialization surfaces. A
    flattened subgraph widget bridge lives in node inputs as a stale
    'resolved' value, and flat_nodes_to_prompt lets it override named values —
    so a retarget that only touched widgets_values_named would silently lose
    to the bridge."""
    set_named(n, key, val)
    wv = n.get('widgets_values')
    if wv:
        names = n.get('widgets_names') or []
        if key in names:
            wv[names.index(key)] = val
    for inp in (n.get('inputs') or []):
        if inp.get('name') == key and 'resolved' in inp:
            inp['resolved'] = val


def cover_resize(src, dst, tw=1344, th=768):
    img = Image.open(src).convert('RGB')
    scale = max(tw / img.width, th / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)),
                     Image.LANCZOS)
    left = (img.width - tw) // 2
    top = (img.height - th) // 2
    img.crop((left, top, left + tw, top + th)).save(dst, 'PNG')
    print(f'[build] {Path(dst).name} <- {Path(src).name} '
          f'{Image.open(dst).size}')


def build_r2v(side):
    """side='A': local r2v as found, turbo switch on, 0.98MP, new prompt.
    side='B': same skeleton, pika ref2va LoRA in, turbo branch deleted,
    lcm + ManualSigmas."""
    wf = load(WF / 'video_minimax_h3_r2v.json')
    n115, n129, n138, n92 = node(wf, 115), node(wf, 129), node(wf, 138), \
        node(wf, 92)
    n115['widgets_values'][1] = MP
    set_named(n115, 'megapixels', MP)
    n138['widgets_values'][0] = R2V_PROMPT
    set_named(n138, 'prompt', R2V_PROMPT)
    set_named(n92, 'filename_prefix', f'video/P56_r2v_{side}')
    n92['widgets_values'][0] = f'video/P56_r2v_{side}'
    set_named(n129, 'noise_seed', SEED)
    n129['widgets_values'][0] = SEED
    # same pre-resized 1344x768 reference pictures as fl2v uses, so Picture 1
    # (first / ref 0) is the boy and Picture 2 (last / ref 1) the kaiju in
    # every scene
    for nid, img in ((137, FIRST_IMG), (139, LAST_IMG)):
        n = node(wf, nid)
        n['widgets_values'][0] = img
        set_named(n, 'image', img)

    if side == 'A':
        n146 = node(wf, 146)
        n146['widgets_values'][0] = True
        set_named(n146, 'value', True)
    else:
        # pika LoRA between UNET (127) and BasicGuider (126); sampler lcm;
        # ManualSigmas replaces BasicScheduler (124); the turbo branch
        # (141-146) is deleted, not switched off — B must not load turbo.
        wf['nodes'] = [n for n in wf['nodes'] if n['id'] not in
                       (141, 142, 143, 144, 145, 146, 124)]
        links = {l[0]: l for l in wf['links']}
        for lid in (283, 284, 285, 286, 287, 288, 289, 290, 291):
            links.pop(lid, None)
        n127 = node(wf, 127)
        n127['outputs'][0]['links'] = [292]
        links[292] = [292, 127, 0, 147, 0, 'MODEL']
        n147 = {
            'id': 147, 'type': 'LoraLoaderModelOnly', 'pos': [100, 4700],
            'size': [320, 90], 'flags': {}, 'order': 20, 'mode': 0,
            'inputs': [{'name': 'model', 'type': 'MODEL', 'link': 292}],
            'outputs': [{'name': 'MODEL', 'type': 'MODEL', 'links': [293]}],
            'properties': {'Node name for S&R': 'LoraLoaderModelOnly'},
            'widgets_values': [PIKA_REF2VA_LORA, 1],
            'widgets_values_named': {'lora_name': PIKA_REF2VA_LORA,
                                     'strength_model': 1},
        }
        wf['nodes'].append(n147)
        links[293] = [293, 147, 0, 126, 0, 'MODEL']
        n126 = node(wf, 126)
        n126['inputs'][0]['link'] = 293

        n148 = {
            'id': 148, 'type': 'ManualSigmas', 'pos': [100, 4860],
            'size': [320, 90], 'flags': {}, 'order': 21, 'mode': 0,
            'inputs': [],
            'outputs': [{'name': 'SIGMAS', 'type': 'SIGMAS', 'links': [256]}],
            'properties': {'Node name for S&R': 'ManualSigmas'},
            'widgets_values': [SIGMAS_STR],
            'widgets_values_named': {'sigmas': SIGMAS_STR},
        }
        wf['nodes'].append(n148)
        links[256] = [256, 148, 0, 125, 3, 'SIGMAS']

        n123 = node(wf, 123)
        n123['widgets_values'][0] = 'lcm'
        set_named(n123, 'sampler_name', 'lcm')
        wf['last_node_id'] = 148
        wf['last_link_id'] = 293
        wf['links'] = list(links.values())
    return wf


def expand_with_prompt(template_name, prompt_text):
    """Load an official template, put our prompt on the wrapper's prompt
    bridge, then flatten subgraphs so inner nodes are directly editable."""
    wf = load(TEMPLATES / template_name)
    wrapper = next(n for n in wf['nodes']
                   if n['type'].startswith('79dd8a95'))
    wrapper.setdefault('widgets_values_named', {})['prompt'] = prompt_text
    if wrapper.get('widgets_values'):
        wrapper['widgets_values'][0] = prompt_text
    flat, notes = expand_subgraphs(wf)
    return {'nodes': flat, 'links': wf.get('links', []),
            '_p56_expanded': True}


def retarget_flat(wf, prefix, first_img=None, last_img=None):
    """Common retargeting of a flattened template: fp16 video VAE, our
    SaveVideo prefix, and (for fl2v) our reference pictures wired to the
    first/last frame bridges. Size comes from ResolutionSelector (t2v) or
    from GetImageSize of the pre-resized first picture (fl2v) — both
    1344x768 by construction."""
    by_type = {}
    for n in wf['nodes']:
        by_type.setdefault(n['type'], []).append(n)
    for n in by_type.get('VAELoader', []):
        if 'minimax_h3_video_vae' in (n.get('widgets_values') or [''])[0]:
            n['widgets_values'][0] = VIDEO_VAE
            set_value(n, 'vae_name', VIDEO_VAE)
    for n in by_type.get('SaveVideo', []):
        n['widgets_values'][0] = prefix
        set_named(n, 'filename_prefix', prefix)
    if first_img or last_img:
        # the flattened MiniMaxH3ImageToVideo carries the frame bridges as
        # resolved [src_id, slot] bindings pointing at the template's own
        # LoadImage nodes — rewire those to ours. The bridge into the
        # first-frame slot is the one the wrapper bound as first_frame;
        # after expansion it is whatever input resolved to the template's
        # first LoadImage. Distinguish by resolve order: first_frame was
        # bound from the subgraph's inputs[0], last from inputs[1].
        av = next(n for n in wf['nodes']
                  if n['type'] == 'MiniMaxH3ImageToVideo')
        img_nodes = {str(n['id']): n for n in wf['nodes']
                     if n['type'] == 'LoadImage'}
        # which resolved source feeds the first-frame input: the one that
        # also appears as the first IMAGE bridge in the subgraph definition
        bridged = [(inp['name'], inp['resolved'])
                   for inp in av.get('inputs', [])
                   if isinstance(inp.get('resolved'), list)
                   and str(inp['resolved'][0]) in img_nodes]
        print(f'[build] frame bridges: {bridged}')
        if len(bridged) >= 2:
            for (name, res), img in zip(bridged, (first_img, last_img)):
                src = img_nodes[str(res[0])]
                src['widgets_values'][0] = img
                set_named(src, 'image', img)
    return wf


def build_fl2v(side):
    wf = expand_with_prompt('video_pika_h3_flex_fl2va.json', FL2V_PROMPT)
    retarget_flat(wf, f'video/P56_fl2v_{side}', first_img=FIRST_IMG,
                  last_img=LAST_IMG)
    if side == 'A':
        # back to the local baseline: turbo_8step LoRA, res_multistep,
        # BasicScheduler(simple, 8). The sigmas node keeps its id so the
        # SamplerCustomAdvanced binding survives untouched.
        inner = {n['id']: n for n in wf['nodes']}
        ks = inner[[i for i in inner if inner[i]['type'] == 'KSamplerSelect']
                   [0]]
        ks['widgets_values'][0] = 'res_multistep'
        set_value(ks, 'sampler_name', 'res_multistep')
        lora = inner[[i for i in inner
                      if inner[i]['type'] == 'LoraLoaderModelOnly'][0]]
        lora['widgets_values'][0] = TURBO_FL_LORA
        set_value(lora, 'lora_name', TURBO_FL_LORA)
        ms_id = [i for i in inner if inner[i]['type'] == 'ManualSigmas'][0]
        ms = inner[ms_id]
        ms.clear()
        ms.update({
            'id': ms_id, 'type': 'BasicScheduler',
            'inputs': [{'name': 'model', 'type': 'MODEL',
                        'resolved': None},
                       {'name': 'steps', 'type': 'INT'},
                       {'name': 'denoise', 'type': 'FLOAT'}],
            'outputs': [{'name': 'SIGMAS', 'type': 'SIGMAS'}],
            'widgets_values': ['simple', 8, 1],
            'widgets_values_named': {'scheduler': 'simple', 'steps': 8,
                                     'denoise': 1},
        })
        # model input: the bare UNET (baseline wires the scheduler to the
        # unpatched model, the guider to the LoRA'd one — same shape as r2v)
        unet_id = [i for i in inner if inner[i]['type'] == 'UNETLoader'][0]
        ms['inputs'][0]['resolved'] = [unet_id, 0]
    return wf


def build_t2v(side):
    if side == 'A':
        wf = load(WF / 'video_minimax_h3_t2v.json')
        wrapper = next(n for n in wf['nodes']
                       if n['type'].startswith('79dd8a95'))
        wrapper.setdefault('widgets_values_named', {})['prompt'] = T2V_PROMPT
        if wrapper.get('widgets_values'):
            wrapper['widgets_values'][0] = T2V_PROMPT
        n115 = node(wf, 115)
        n115['widgets_values'][1] = MP
        set_named(n115, 'megapixels', MP)
        n92 = node(wf, 92)
        n92['widgets_values'][0] = 'video/P56_t2v_A'
        set_named(n92, 'filename_prefix', 'video/P56_t2v_A')
        flat, _ = expand_subgraphs(wf)
        return {'nodes': flat, 'links': wf.get('links', []),
                '_p56_expanded': True}
    wf = expand_with_prompt('video_pika_h3_flex_t2v.json', T2V_PROMPT)
    return retarget_flat(wf, 'video/P56_t2v_B')


def audit(name, wf, expect):
    """Convert to an API prompt and assert the load-bearing values."""
    prompt = to_prompt(wf, SEED)
    by_class = {}
    for nid, n in prompt.items():
        by_class.setdefault(n['class_type'], []).append(n['inputs'])
    failures = []
    for class_type, pred in expect.items():
        hits = by_class.get(class_type, [])
        if not any(pred(inp) for inp in hits):
            failures.append(f'{class_type}: none of {len(hits)} matches '
                            f'(got {str(hits)[:300]})')
    if failures:
        raise SystemExit(f'[audit] {name} FAILED:\n  ' +
                         '\n  '.join(failures))
    print(f'[audit] {name} ok ({len(prompt)} API nodes)')
    return prompt


def main():
    cover_resize(COMFY_INPUT / FIRST_SRC, COMFY_INPUT / FIRST_IMG)
    cover_resize(COMFY_INPUT / LAST_SRC, COMFY_INPUT / LAST_IMG)

    built = {}
    for side in ('A', 'B'):
        name = f'video_p56_r2v_{side}_{"turbo" if side == "A" else "flex"}'
        built[name] = build_r2v(side)
        save(built[name], WF / f'{name}.json')
    for side in ('A', 'B'):
        name = f'video_p56_fl2v_{side}_{"turbo" if side == "A" else "flex"}'
        built[name] = build_fl2v(side)
        save(built[name], WF / f'{name}.json')
    for side, tag in (('A', 'full'), ('B', 'flex')):
        name = f'video_p56_t2v_{side}_{tag}'
        built[name] = build_t2v(side)
        save(built[name], WF / f'{name}.json')

    common = {
        'RandomNoise': lambda i: i.get('noise_seed') == SEED,
        'VAELoader': lambda i: i.get('vae_name') == VIDEO_VAE,
    }
    sized = {**common,
             'ResolutionSelector': lambda i: i.get('megapixels') == MP}
    audit('r2v_A', built['video_p56_r2v_A_turbo'], {
        **common,
        'PrimitiveBoolean': lambda i: i.get('value') is True,
        'LoraLoaderModelOnly': lambda i: i.get('lora_name') == TURBO_REF_LORA,
        'PrimitiveInt': lambda i: i.get('value') == 4,
        'KSamplerSelect': lambda i: i.get('sampler_name') == 'res_multistep',
        'LoadImage': lambda i: i.get('image') in (FIRST_IMG, LAST_IMG),
    })
    audit('r2v_B', built['video_p56_r2v_B_flex'], {
        **common,
        'LoraLoaderModelOnly': lambda i: i.get('lora_name') == PIKA_REF2VA_LORA,
        'KSamplerSelect': lambda i: i.get('sampler_name') == 'lcm',
        'ManualSigmas': lambda i: i.get('sigmas') == SIGMAS_STR,
        'LoadImage': lambda i: i.get('image') in (FIRST_IMG, LAST_IMG),
    })
    audit('fl2v_A', built['video_p56_fl2v_A_turbo'], {
        **common,
        'LoraLoaderModelOnly': lambda i: i.get('lora_name') == TURBO_FL_LORA,
        'KSamplerSelect': lambda i: i.get('sampler_name') == 'res_multistep',
        'BasicScheduler': lambda i: i.get('steps') == 8
        and i.get('scheduler') == 'simple',
        'LoadImage': lambda i: i.get('image') in (FIRST_IMG, LAST_IMG),
    })
    audit('fl2v_B', built['video_p56_fl2v_B_flex'], {
        **common,
        'LoraLoaderModelOnly': lambda i: i.get('lora_name') == PIKA_FL2VA_LORA,
        'KSamplerSelect': lambda i: i.get('sampler_name') == 'lcm',
        'ManualSigmas': lambda i: i.get('sigmas') == SIGMAS_STR,
        'LoadImage': lambda i: i.get('image') in (FIRST_IMG, LAST_IMG),
    })
    audit('t2v_A', built['video_p56_t2v_A_full'], {
        **common,
        'PrimitiveBoolean': lambda i: i.get('value') is False,
        'PrimitiveInt': lambda i: i.get('value') == 20,
    })
    audit('t2v_B', built['video_p56_t2v_B_flex'], {
        **common,
        'LoraLoaderModelOnly': lambda i: i.get('lora_name') == PIKA_FL2VA_LORA,
        'KSamplerSelect': lambda i: i.get('sampler_name') == 'lcm',
        'ManualSigmas': lambda i: i.get('sigmas') == SIGMAS_STR,
    })
    print('[build] all six workflows built and audited')


if __name__ == '__main__':
    main()
