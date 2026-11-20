"""Picture lock for liaozhai_demo: title card -> shots -> end card -> concat.

All intermediates: 864x480 24fps yuv420p h264 -bf 0 (B-free per the
xfade/concat lesson in the env notes), no audio.
Output: 07_edit/LZ_PICTURE_LOCK_864x480.mp4
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
EDIT = PROJECT / '07_edit'
NORM = EDIT / 'norm'
CFG = json.loads((PROJECT / '00_project/story.json').read_text(encoding='utf-8'))
ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10']
TITLECARD = CFG['titlecard_duration_s']
ENDCARD = CFG['endcard_duration_s']
W, H, FPS = CFG['width'], CFG['height'], CFG['fps']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(r.stderr.decode()[-1500:])
        raise SystemExit(1)


def enc_args():
    return ['-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
            '-bf', '0', '-pix_fmt', 'yuv420p', '-an']


def normalize(sid):
    tag = CFG.get('gen_tag', 'T01')
    src = PROJECT / '03_video_raw' / sid / f'{sid}_{tag}.mp4'
    dst = NORM / f'{sid}.mp4'
    if not src.exists():
        print(f'ERROR: missing {src}')
        raise SystemExit(1)
    vf = f'scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-vf', vf] + enc_args() + [str(dst)])
    return dst


def card_png(name, seed, glow_y=0.30):
    """Dark night gradient card with film grain and a faint candle glow."""
    png = EDIT / f'{name}_1080p.png'
    if png.exists():
        return png
    w, h = 1920, 1080
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.5, h * glow_y
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (h * 0.95)
    r = np.clip(r, 0, 1)
    base = np.stack([10 + 13 * (1 - r), 16 + 18 * (1 - r), 30 + 30 * (1 - r)], -1)
    glow = np.exp(-(((xx - cx) / (w * 0.28)) ** 2 + ((yy - h * 0.42) / (h * 0.30)) ** 2))
    base += np.stack([26 * glow, 17 * glow, 5 * glow], -1)
    grain = np.random.default_rng(seed).normal(0, 1.2, (h, w, 1))
    Image.fromarray(np.clip(base + grain, 0, 255).astype(np.uint8), 'RGB').save(png)
    return png


def card_segment(name, duration, seed, glow_y=0.30):
    png = card_png(name, seed, glow_y)
    dst = NORM / f'{name}.mp4'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-t', str(duration),
         '-r', str(FPS), '-i', str(png),
         '-vf', f'scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}'] + enc_args() + [str(dst)])
    return dst


def main():
    t0 = time.time()
    NORM.mkdir(parents=True, exist_ok=True)
    segs = [card_segment('TITLECARD', TITLECARD, 20260924)]
    segs += [normalize(sid) for sid in ORDER]
    segs.append(card_segment('ENDCARD', ENDCARD, 20260925, glow_y=0.55))

    listing = EDIT / 'concat_list.txt'
    listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in segs), encoding='utf-8')
    lock = EDIT / f'LZ_PICTURE_LOCK_{W}x{H}.mp4'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
         '-i', str(listing), '-c', 'copy', str(lock)])

    dur = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(lock)]).decode().strip()
    print(f'picture lock: {lock} ({float(dur):.2f}s, {lock.stat().st_size/1e6:.1f}MB, '
          f'{time.time()-t0:.0f}s)')


if __name__ == '__main__':
    main()
