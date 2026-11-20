"""Picture lock: normalize all takes -> S02 freeze extension -> end card -> concat.

All intermediates: 864x480 24fps yuv420p h264 -bf 0 (B-free per the xfade/concat
lesson in the env notes), no audio (music/voice come from the mix stage).
Output: 07_edit/PIYAO_PICTURE_LOCK_864x480.mp4
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

PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
EDIT = PROJECT / '07_edit'
NORM = EDIT / 'norm'
CFG = json.loads((PROJECT / '00_project/shots.json').read_text(encoding='utf-8'))
ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08',
         'S09', 'S10', 'S11', 'S12', 'S13', 'S14']
FREEZE = CFG.get('s02_freeze_extra_s', 2.0)
ENDCARD = CFG.get('endcard_duration_s', 4.5)
W, H, FPS = CFG['width'], CFG['height'], CFG['fps']


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(r.stderr.decode()[-1500:])
        sys.exit(1)


def enc_args():
    return ['-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
            '-bf', '0', '-pix_fmt', 'yuv420p', '-an']


def normalize(sid):
    src = PROJECT / '03_video_raw' / sid / f'{sid}_T01.mp4'
    dst = NORM / f'{sid}.mp4'
    if not src.exists():
        print(f'ERROR: missing {src}')
        sys.exit(1)
    vf = f'scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}'
    if sid == 'S02':
        vf += f',tpad=stop_mode=clone:stop_duration={FREEZE}'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-vf', vf] + enc_args() + [str(dst)])
    return dst


def make_endcard():
    """Clean dark gradient card; all text is burned later at native 1080p."""
    png = EDIT / 'endcard_1080p.png'
    if png.exists():
        return png
    w, h = 1920, 1080
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.5, h * 0.30
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (h * 0.95)
    r = np.clip(r, 0, 1)
    base = np.stack([11 + 14 * (1 - r), 21 + 20 * (1 - r), 38 + 32 * (1 - r)], -1)
    grain = np.random.default_rng(20260922).normal(0, 1.2, (h, w, 1))
    img = np.clip(base + grain, 0, 255).astype(np.uint8)
    Image.fromarray(img, 'RGB').save(png)
    return png


def endcard_segment():
    png = make_endcard()
    dst = NORM / 'ENDCARD.mp4'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-t', str(ENDCARD),
         '-r', str(FPS), '-i', str(png),
         '-vf', f'scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}'] + enc_args() + [str(dst)])
    return dst


def main():
    t0 = time.time()
    NORM.mkdir(parents=True, exist_ok=True)
    segs = [normalize(sid) for sid in ORDER]
    segs.append(endcard_segment())

    listing = EDIT / 'concat_list.txt'
    listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in segs), encoding='utf-8')
    lock = EDIT / 'PIYAO_PICTURE_LOCK_864x480.mp4'
    run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
         '-i', str(listing), '-c', 'copy', str(lock)])

    dur = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(lock)]).decode().strip()
    print(f'picture lock: {lock} ({float(dur):.2f}s, {lock.stat().st_size/1e6:.1f}MB, '
          f'{time.time()-t0:.0f}s)')


if __name__ == '__main__':
    main()
