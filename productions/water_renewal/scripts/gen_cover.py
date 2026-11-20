"""Generate cover base footage with MiniMax H3 (higher-res 1280x736), then
pick the best frame for the video cover."""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_h3_clips as g  # reuse graph builder + server helpers

g.W, g.H = 1280, 736      # 0.9MP 16:9 (per workflow size table)
OUT = Path(r'E:/promo_video/assets/cover')
OUT.mkdir(parents=True, exist_ok=True)

PROMPT = ("Cinematic environmental documentary shot, elevated view of a narrow urban river in China: "
          "thousands of extremely fine micro bubbles form a soft white cloud blooming across the water "
          "surface from an aeration unit, gray-green turbid water with gentle ripples, weeping willow "
          "branches framing the top edge, a small blue work boat moored at the far bank, soft overcast "
          "morning light, realistic physics, restrained blue-gray-green palette, photorealistic, high "
          "detail, no text, no labels, no people, 16:9.")


def log(m):
    print(f'[{time.strftime("%H:%M:%S")}] {m}', flush=True)


def main():
    slug, seed = 'cover_base', 2026092203
    dst = OUT / f'{slug}.mp4'
    if dst.exists() and dst.stat().st_size > 200_000:
        log('exists, skip')
        return
    length = g.h3_length(6.5)
    log(f'GEN cover: {length} frames @ {g.W}x{g.H}, seed={seed}')
    resp = g.api('/prompt', {'prompt': g.build_graph(PROMPT, seed, length)})
    if 'error' in resp:
        log(f'ERROR: {resp["error"]}')
        sys.exit(1)
    pid = resp['prompt_id']
    t0 = time.time()
    while True:
        h = g.api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                log(f'FAILED: {str(st.get("messages"))[-400:]}')
                sys.exit(1)
            if st.get('completed') or 'outputs' in rec:
                break
        time.sleep(5)
    log(f'done in {time.time()-t0:.0f}s')
    src = None
    for node_out in (rec.get('outputs') or {}).values():
        for key in ('videos', 'images', 'gifs'):
            for item in (node_out.get(key) or []):
                if item.get('filename'):
                    cand = Path(r'E:/Minimax-H3/third_party/ComfyUI/output') / (item.get('subfolder') or '') / item['filename']
                    if cand.exists():
                        src = cand
    shutil.copy2(src, dst)
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height,nb_frames',
                        '-of', 'csv=p=0', str(dst)], capture_output=True, text=True)
    log(f'saved {dst} {r.stdout.strip()}')


if __name__ == '__main__':
    main()
