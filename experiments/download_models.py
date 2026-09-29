"""Robust MiniMax-H3 model downloader with real-time progress."""
import os
import sys
import time
import requests
from pathlib import Path

# Proxy + disable HF-specific behavior
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

REPO = 'Comfy-Org/MiniMax-H3'
# Use raw Windows path to avoid Git Bash /e/... prefix confusion
LOCAL_DIR = Path(r'E:\ComfyUI\models')

FILES = [
    # HF API reports sizes in bytes; convert GB (10^9) → bytes for comparison.
    # On-disk size from stat() is in bytes, so this matches directly.
    ('diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors', 20.97 * 1e9),
    ('diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors', 20.97 * 1e9),
    ('text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors',         15.69 * 1e9),
    ('loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors',     1.96 * 1e9),
    ('loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors',   1.96 * 1e9),
]

def fmt(sz):
    for u in ['B','KB','MB','GB']:
        if sz < 1024: return f'{sz:.1f}{u}'
        sz /= 1024
    return f'{sz:.1f}TB'

def download_one(rel_path, expected_size):
    target = LOCAL_DIR / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/{REPO}/resolve/main/{rel_path}'

    # Resume support
    existing = target.stat().st_size if target.exists() else 0
    if existing >= expected_size * 0.99:
        print(f'[skip] {rel_path}  already {fmt(existing)}')
        return

    print(f'\n[download] {rel_path}')
    print(f'  url: {url}')
    print(f'  target: {target}')
    print(f'  resuming from: {fmt(existing)} / {fmt(expected_size)}')

    headers = {}
    if existing > 0:
        headers['Range'] = f'bytes={existing}-'

    sess = requests.Session()
    sess.proxies = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}

    t0 = time.time()
    last_report = t0
    last_size = existing
    bytes_written = existing

    try:
        resp = sess.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True)
        resp.raise_for_status()

        # If server returned 200 (not 206), it's starting from scratch
        if resp.status_code == 200:
            existing = 0
            bytes_written = 0
            target.unlink(missing_ok=True)

        mode = 'ab' if existing > 0 else 'wb'
        with open(target, mode) as f:
            for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):  # 4 MB chunks
                if not chunk:
                    continue
                f.write(chunk)
                bytes_written += len(chunk)

                now = time.time()
                if now - last_report >= 10:
                    delta = bytes_written - last_size
                    dt = now - last_report
                    speed = delta / dt / 1e6  # MB/s
                    pct = bytes_written / expected_size * 100
                    eta_sec = (expected_size - bytes_written) / (delta/dt) if delta > 0 else 0
                    print(f'  [{pct:5.1f}%] {fmt(bytes_written)}/{fmt(expected_size)}  '
                          f'{speed:.2f} MB/s  ETA {eta_sec/60:.0f} min', flush=True)
                    last_report = now
                    last_size = bytes_written

        elapsed = time.time() - t0
        sz = target.stat().st_size
        print(f'[done]   {rel_path}  {fmt(sz)}  in {elapsed/60:.1f} min  '
              f'(avg {sz/elapsed/1e6:.2f} MB/s)')
    except Exception as e:
        print(f'[FAIL]   {rel_path}: {e}')
        print(f'  partially downloaded: {fmt(bytes_written)} -- rerun to resume')
        sys.exit(1)

for f, sz in FILES:
    download_one(f, sz)

print('\n=== ALL DONE ===')
