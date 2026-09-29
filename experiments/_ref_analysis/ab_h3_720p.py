"""A/B: H3 at native-ish 1280x720 - 20-step full quality vs 8-step 768p turbo.

Usage:
  python ab_h3_720p.py full    # 20 steps, no LoRA, default shift 12/3
  python ab_h3_720p.py turbo   # 8 steps, 768p LoRA, shift 6/3
"""
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
COMFY_OUTPUT = Path(r'E:/ComfyUI/output')
OUT = Path(r'E:/Minimax-H3/_ref_analysis')

W, H, FPS = 1280, 720, 24
CLIP = 'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
UNET = 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
LORA_768 = 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'
LENGTH = 175  # 7.29s, L%17==5

PROMPT = ('佛殿阴影深处，一位穿青白上衣红裙、黑发挽髻的年轻女子缓缓走出，双手合掌行礼求助，'
          '神情柔弱无助，烛光摇曳，纱幔轻晃。上美影厂复古赛璐璐手绘动画风格，上世纪五十年代'
          '中国学派老动画质感，线条干净，色块平整，水墨晕染背景，胶片颗粒，经典手绘动画。')


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


def submit(graph):
    resp = api('/prompt', {'prompt': graph})
    if 'error' in resp:
        raise RuntimeError(f'submit error: {resp["error"]}')
    return resp['prompt_id']


def wait_for(pid):
    t0 = time.time()
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                raise RuntimeError(f'FAILED: {str(st.get("messages"))[-800:]}')
            if st.get('completed') or 'outputs' in rec:
                return rec, time.time() - t0
        time.sleep(5)


def graph_for(mode):
    def n(cls, **inp):
        return {'class_type': cls, 'inputs': inp}

    steps = 20 if mode == 'full' else 8
    g = {
        '128': n('CLIPLoader', clip_name=CLIP, type='minimax', device='default'),
        '127': n('UNETLoader', unet_name=UNET, weight_dtype='default'),
        '119': n('VAELoader', vae_name='minimax_h3_video_vae_fp16.safetensors'),
        '120': n('VAELoader', vae_name='minimax_h3_audio_vae_fp32.safetensors'),
        '131': n('MiniMaxH3ImageToVideo', clip=['128', 0], vae=['119', 0],
                 prompt=PROMPT, width=W, height=H, length=LENGTH),
        '129': n('RandomNoise', noise_seed=731904),
        '123': n('KSamplerSelect', sampler_name='res_multistep'),
        '124': n('BasicScheduler', model=None, steps=steps, denoise=1.0, scheduler='simple'),
        '126': n('BasicGuider', model=None, conditioning=['131', 0]),
        '125': n('SamplerCustomAdvanced', noise=['129', 0], guider=['126', 0],
                 sampler=['123', 0], sigmas=['124', 0], latent_image=['131', 1]),
        '122': n('VAEDecode', samples=['125', 0], vae=['119', 0]),
        '121': n('VAEDecodeAudio', samples=['125', 0], vae=['120', 0]),
        '130': n('CreateVideo', images=['122', 0], audio=['121', 0], fps=FPS, bit_depth=8),
        '92': n('SaveVideo', video=['130', 0], filename_prefix=f'ab720_{mode}', format='auto'),
    }
    if mode == 'full':
        g['134'] = None
        del g['134']
        g['124']['inputs']['model'] = ['127', 0]
        g['126']['inputs']['model'] = ['127', 0]
        # default shift (12/3) from node defaults: no SigmaShift node
    else:
        g['134'] = n('LoraLoaderModelOnly', model=['127', 0], lora_name=LORA_768,
                     strength_model=1.0)
        g['124']['inputs']['model'] = ['134', 0]
        g['126']['inputs']['model'] = ['134', 0]
        g['135'] = n('MiniMaxH3SigmaShift', model=['134', 0],
                     shift_video=6.0, shift_audio=3.0)
        g['124']['inputs']['model'] = ['135', 0]
        g['126']['inputs']['model'] = ['135', 0]
    return g


def main():
    mode = sys.argv[1]
    pid = submit(graph_for(mode))
    print(f'[{time.strftime("%H:%M:%S")}] submitted {mode}: {pid}', flush=True)
    rec, wall = wait_for(pid)
    found = []
    for node_out in (rec.get('outputs') or {}).values():
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(COMFY_OUTPUT / sub / item['filename'])
    src = next((c for c in found if c.exists()), None)
    dst = OUT / f'ab720_{mode}.mp4'
    shutil.copy2(src, dst)
    print(f'{mode} done in {wall:.0f}s -> {dst}')


if __name__ == '__main__':
    main()
