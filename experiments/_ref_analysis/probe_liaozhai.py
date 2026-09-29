"""Style probe: can our H3 pipeline reproduce the 涛涛狐言《鬼新娘》 look?

Two 864x480 probes queued back-to-back, then x4v3 upscale to 1920x1080:
  P1 t2v - pure prompt, no reference (baseline style adherence)
  P2 r2v - Picture 1 = a real frame lifted from the reference video
           (the consistency path we'd use in production)
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
R2V_WORKFLOW = Path(r'E:/Minimax-H3/video_minimax_h3_r2v.json')
COMFY_INPUT = Path(r'E:/ComfyUI/input')
COMFY_OUTPUT = Path(r'E:/ComfyUI/output')
OUT = Path(r'E:/Minimax-H3/_ref_analysis')

W, H, FPS, STEPS = 864, 480, 24, 8
CLIP = 'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
UNET = 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
LORA = 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'
LENGTH = 141  # 5.875s, L%17==5

PROMPT = ('上美影厂复古赛璐璐手绘动画风格，1958年老动画质感。深夜古寺卧房内烛光摇曳，'
          '一位穿蓝白明朝书生袍、白玉发簪的年轻书生双手抱拳躬身作揖，对着面前背对镜头的'
          '红衣女子恭敬说话，嘴部随话语自然开合，神情诚恳带愧。纱帐、木格窗、水彩晕染背景，'
          '线条干净，色块平整，胶片颗粒，经典中国学派手绘动画。')

REF_FRAME = OUT / 'f_162.png'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, data=None, timeout=7200):
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


def wait_server():
    for i in range(120):
        try:
            api('/system_stats')
            return
        except Exception:
            time.sleep(5)
    raise RuntimeError('ComfyUI did not come up in 10 min')


def wait_for(pid):
    t0 = time.time()
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                raise RuntimeError(f'FAILED: {str(st.get("messages"))[-500:]}')
            if st.get('completed') or 'outputs' in rec:
                return rec, time.time() - t0
        time.sleep(5)


def submit(graph):
    resp = api('/prompt', {'prompt': graph})
    if 'error' in resp:
        raise RuntimeError(f'submit error: {resp["error"]}')
    return resp['prompt_id']


def outputs_from_history(rec):
    found = []
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(COMFY_OUTPUT / sub / item['filename'])
    return found


def build_t2v_graph(prompt, seed, length):
    def n(cls, **inp):
        return {'class_type': cls, 'inputs': inp}

    return {
        '128': n('CLIPLoader', clip_name=CLIP, type='minimax', device='default'),
        '127': n('UNETLoader', unet_name=UNET, weight_dtype='default'),
        '134': n('LoraLoaderModelOnly', model=['127', 0], lora_name=LORA, strength_model=1.0),
        '119': n('VAELoader', vae_name='minimax_h3_video_vae_fp16.safetensors'),
        '120': n('VAELoader', vae_name='minimax_h3_audio_vae_fp32.safetensors'),
        '131': n('MiniMaxH3ImageToVideo', clip=['128', 0], vae=['119', 0],
                 prompt=prompt, width=W, height=H, length=length),
        '129': n('RandomNoise', noise_seed=seed),
        '123': n('KSamplerSelect', sampler_name='res_multistep'),
        '124': n('BasicScheduler', model=['134', 0], steps=STEPS, denoise=1.0, scheduler='simple'),
        '126': n('BasicGuider', model=['134', 0], conditioning=['131', 0]),
        '125': n('SamplerCustomAdvanced', noise=['129', 0], guider=['126', 0],
                 sampler=['123', 0], sigmas=['124', 0], latent_image=['131', 1]),
        '122': n('VAEDecode', samples=['125', 0], vae=['119', 0]),
        '121': n('VAEDecodeAudio', samples=['125', 0], vae=['120', 0]),
        '130': n('CreateVideo', images=['122', 0], audio=['121', 0], fps=FPS, bit_depth=8),
        '92': n('SaveVideo', video=['130', 0], filename_prefix='probe_t2v', format='auto'),
    }


def build_r2v_graph(prompt, seed, length, ref_file):
    wf = json.loads(R2V_WORKFLOW.read_text(encoding='utf-8'))
    link_map = {l[0]: (l[1], l[2]) for l in wf.get('links', [])}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    graph = {}
    for n in wf.get('nodes', []):
        if n.get('type') in SKIP:
            continue
        nid = str(n['id'])
        inputs = {}
        inputs.update(n.get('widgets_values_named') or {})
        names = n.get('widgets_names') or []
        values = n.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]
        if nid == '136':
            inputs['length'] = length
            inputs['noise_seed'] = seed
            inputs['prompt'] = prompt
            inputs['width'] = W
            inputs['height'] = H
        if nid == '138':
            inputs['value'] = prompt
        if nid == '137':
            inputs['image'] = ref_file
        if nid == '132':
            inputs['value'] = length / 24.0
        for inp in (n.get('inputs') or []):
            lid, name = inp.get('link'), inp.get('name')
            if lid is None or name is None or name in inputs:
                continue
            if lid in link_map:
                src_id, src_slot = link_map[lid]
                inputs[name] = [str(src_id), src_slot]
        graph[nid] = {'class_type': n['type'], 'inputs': inputs}
    return graph


def main():
    wait_server()
    log('ComfyUI up, queueing probes')

    ref_name = 'probe_ref_guixinniang.png'
    shutil.copy2(REF_FRAME, COMFY_INPUT / ref_name)

    g1 = build_t2v_graph(PROMPT, seed=20260924, length=LENGTH)
    g2 = build_r2v_graph(PROMPT, seed=20260924, length=LENGTH, ref_file=ref_name)
    p1, p2 = submit(g1), submit(g2)
    log(f'queued t2v={p1} r2v={p2}')

    for tag, pid in (('t2v', p1), ('r2v', p2)):
        rec, wall = wait_for(pid)
        src = next((c for c in outputs_from_history(rec) if c.exists()), None)
        if src is None:
            raise RuntimeError(f'{tag}: no output')
        dst = OUT / f'probe_{tag}_480.mp4'
        shutil.copy2(src, dst)
        log(f'{tag} done in {wall:.0f}s -> {dst}')

    # upscale both to 1080p
    for tag in ('t2v', 'r2v'):
        src, dst = OUT / f'probe_{tag}_480.mp4', OUT / f'probe_{tag}_1080.mp4'
        subprocess.run([sys.executable, r'E:/Minimax-H3/sr_pipeline_v2.py',
                        str(src), str(dst), '--model', 'x4v3', '--scale', '4',
                        '--out-width', '1920', '--out-height', '1080'], check=True)
        log(f'{tag} upscaled -> {dst}')

    # side-by-side: reference frame vs our upscaled frames
    ff = r'E:/Minimax-H3/tools/ffmpeg-7.1.1-full_build/bin/ffmpeg.exe'
    for tag in ('t2v', 'r2v'):
        subprocess.run([ff, '-y', '-v', 'error', '-ss', '3', '-i',
                        str(OUT / f'probe_{tag}_1080.mp4'), '-frames:v', '1',
                        str(OUT / f'probe_{tag}_frame.png')], check=True)
    inputs = []
    for f in ('f_162.png', 'probe_r2v_frame.png', 'probe_t2v_frame.png'):
        inputs += ['-i', str(OUT / f)]
    subprocess.run([ff, '-y', '-v', 'error'] + inputs + ['-filter_complex',
                   '[0][1][2]hstack=3,scale=2880:-1', str(OUT / 'compare.jpg')], check=True)
    log('compare sheet -> compare.jpg (ref | ours-r2v | ours-t2v)')


if __name__ == '__main__':
    main()
