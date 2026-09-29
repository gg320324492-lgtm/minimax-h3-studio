"""SeedVR2 ComfyUI workflow test - video upscale via diffusion."""
import json, shutil, sys, time
import urllib.request, urllib.error
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
INPUT_VIDEO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4')
OUTPUT_VIDEO = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(r'E:\Minimax-H3\seedvr2_test.mp4')
SEED = 42


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


def build_workflow():
    """Build SeedVR2 upscale workflow. Connections:
      LoadVideo(1) -> GetVideoComponents(2) -> images[0] + audio[1]
      Preprocess(3) takes images
      VAEEncode(4) takes preprocessed + VAE(10)
      SeedVR2Conditioning(6) takes model(5) + latent(4)
      KSampler(7) takes model + conditioning + latent
      VAEDecode(8) takes sampled + VAE
      SeedVR2PostProcessing(9) takes decoded + original_resized
      CreateVideo(11) takes post-processed + audio
      SaveVideo(12) takes the video
    """
    return {
        "1": {"class_type": "LoadVideo", "inputs": {"file": INPUT_VIDEO.name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["2", 0]}},
        "5": {"class_type": "UNETLoader", "inputs": {"unet_name": "seedvr2_ema_3b.safetensors", "weight_dtype": "default"}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "ema_vae.pth"}},
        "4": {"class_type": "VAEEncode", "inputs": {"pixels": ["3", 0], "vae": ["10", 0]}},
        "6": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["5", 0], "vae_conditioning": ["4", 0]}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["5", 0], "seed": SEED, "steps": 1, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "normal",
            "positive": ["6", 0], "negative": ["6", 1],
            "latent_image": ["4", 0], "denoise": 1.0
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SeedVR2PostProcessing", "inputs": {
            "images": ["8", 0], "original_resized_images": ["2", 0], "color_correction_method": "lab"
        }},
        "11": {"class_type": "CreateVideo", "inputs": {
            "images": ["9", 0], "fps": ["2", 2], "audio": ["2", 1]
        }},
        "12": {"class_type": "SaveVideo", "inputs": {
            "video": ["11", 0], "filename_prefix": "SeedVR2_test", "format": "auto"
        }}
    }


def find_output_video():
    out_dir = Path(r'E:\ComfyUI\output\video')
    files = list(out_dir.glob('SeedVR2_test*.mp4'))
    if not files:
        files = list(Path(r'E:\ComfyUI\output').rglob('*.mp4'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def main():
    log(f'Input:  {INPUT_VIDEO}')
    log(f'Output: {OUTPUT_VIDEO}')

    if not INPUT_VIDEO.exists():
        log('ERROR: input not found'); return

    log('Building workflow...')
    workflow = build_workflow()

    log('Submitting...')
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': workflow})
    if 'error' in resp:
        log(f'ERROR: {resp["error"]["type"]}: {resp["error"]["message"]}')
        if resp.get('node_errors'):
            for nid, e in resp['node_errors'].items():
                log(f'  node {nid}: {e}')
        return
    pid = resp.get('prompt_id')
    log(f'pid={pid}')

    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            if rec.get('status', {}).get('completed') or 'outputs' in rec:
                wall = time.time() - t0
                log(f'DONE in {wall:.1f}s'); break
            st = rec.get('status', {}).get('status_str')
            if st in ('error', 'failed'):
                log(f'FAILED after {time.time()-t0:.1f}s')
                log(json.dumps(rec, indent=2)[:2000])
                return
        time.sleep(5)

    time.sleep(3)
    src = find_output_video()
    if not src:
        log('No output video found'); return
    log(f'Found: {src} ({src.stat().st_size/1e6:.1f}MB)')
    shutil.copy2(str(src), str(OUTPUT_VIDEO))
    log(f'Saved: {OUTPUT_VIDEO}')

if __name__ == '__main__':
    main()