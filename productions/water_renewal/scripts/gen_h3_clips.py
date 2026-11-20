"""Generate the two H3 science-animation clips for the promo (pure t2v).

Flattened API graph replicated from the t2v subgraph:
CLIPLoader(qwen3vl) + UNETLoader(fl2va int8) -> turbo 8step LoRA ->
MiniMaxH3ImageToVideo(prompt, WxH, length) -> SamplerCustomAdvanced ->
VAEDecode + VAEDecodeAudio -> CreateVideo(24fps) -> SaveVideo.

length must satisfy L % 17 == 5 (H3 temporal block alignment), same rule as
the workflow's ComfyMathExpression.
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
PROJECT = Path(r'E:/Minimax-H3/productions/water_renewal')
OUT_DIR = PROJECT / 'assets' / 'h3'
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 864, 480          # 0.4MP 16:9 (per workflow size table)
FPS = 24
STEPS = 8                # turbo LoRA deployed at 8 steps (repo A/B result)

CLIP = 'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
UNET = 'minimax_h3_fl2va_pruned_int8_convrot.safetensors'
LORA = 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'

CLIPS = [
    ('H3A_mass_transfer', 8.0, 2026092201, """A scientifically accurate cinematic visualization inside turbid polluted river water. Thousands of extremely small micro and nano bubbles are dispersed throughout the water column rather than rapidly rising like large bubbles. The bubbles move slowly with realistic fluid motion, creating a large gas-liquid interfacial area. Subtle oxygen molecules diffuse from the bubbles into the surrounding water. Dark gray-green polluted water gradually becomes more oxygen-rich locally, but do NOT show the entire water magically becoming clear. Environmental engineering documentary aesthetic, realistic physics, microscopic scientific visualization, slow forward camera movement, restrained blue-white highlights, no text, no labels, no people, no fantasy effects, 16:9."""),
    ('H3B_sediment_interface', 8.0, 2026092202, """Scientific cross-sectional visualization of a polluted urban river sediment-water interface. Dark organic-rich sediment is visible at the bottom, with turbid water above it. Micro-nano bubbles move close to the sediment-water interface. Subtle oxygen transfer and oxidation reactions occur around the bubbles and at the sediment surface. Some pollutants are visualized as abstract molecular particles moving between sediment and overlying water, with their release gradually being suppressed near the treated interface. Realistic environmental engineering visualization, scientifically restrained, no magical cleanup, no crystal-clear transformation, no text, no labels, cinematic documentary quality, 16:9."""),
]


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, data=None, timeout=3600):
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


def h3_length(seconds: float) -> int:
    l0 = max(5, round(seconds * FPS))
    return l0 + (5 - (l0 % 17)) % 17


def build_graph(prompt, seed, length):
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
        '92': n('SaveVideo', video=['130', 0], filename_prefix='promo_h3', format='auto'),
    }


def main():
    only = sys.argv[1:] or None
    for slug, seconds, seed, prompt in CLIPS:
        if only and slug not in only:
            continue
        dst = OUT_DIR / f'{slug}.mp4'
        if dst.exists() and dst.stat().st_size > 200_000:
            log(f'SKIP {slug} (exists)')
            continue
        length = h3_length(seconds)
        log(f'GEN {slug}: {length} frames ({length/FPS:.2f}s), seed={seed}')
        resp = api('/prompt', {'prompt': build_graph(prompt, seed, length)})
        if 'error' in resp:
            log(f'ERROR: {resp["error"]}')
            return 1
        pid = resp['prompt_id']
        t0 = time.time()
        while True:
            h = api(f'/history/{pid}')
            if pid in h:
                rec = h[pid]
                st = rec.get('status', {})
                if st.get('status_str') in ('error', 'failed'):
                    log(f'FAILED: {str(st.get("messages"))[-400:]}')
                    return 1
                if st.get('completed') or 'outputs' in rec:
                    break
            time.sleep(5)
        log(f'  done in {time.time()-t0:.0f}s')
        src = None
        for node_out in (rec.get('outputs') or {}).values():
            for item in (node_out.get('videos') or []) + (node_out.get('images') or []) + (node_out.get('gifs') or []):
                if item.get('filename'):
                    cand = Path(r'E:/Minimax-H3/third_party/ComfyUI/output') / (item.get('subfolder') or '') / item['filename']
                    if cand.exists():
                        src = cand
        if not src:
            log('no output file found in history')
            return 1
        shutil.copy2(src, dst)
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height,nb_frames,duration',
             '-of', 'csv=p=0', str(dst)], capture_output=True, text=True)
        log(f'  saved {dst} ({dst.stat().st_size/1e6:.1f} MB) {probe.stdout.strip()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
