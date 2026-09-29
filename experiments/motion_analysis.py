"""Motion analysis - quantify where motion happens in the generated video."""
import sys
import subprocess
from pathlib import Path
from PIL import Image
import numpy as np
import os

FRAMES_DIR = Path(r'E:\Minimax-H3\work_frames\motion')

def extract(video_path, name, fps=4):
    for f in FRAMES_DIR.glob(f'{name}_*.png'): f.unlink()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-i', str(video_path),
        '-vf', f'fps={fps},scale=336:192',
        str(FRAMES_DIR / f'{name}_%02d.png')
    ], check=True)

def analyze(name, fps=4):
    files = sorted(FRAMES_DIR.glob(f'{name}_*.png'),
                   key=lambda p: int(p.stem.split('_')[1]))
    if not files:
        print(f'No frames for {name}')
        return
    imgs = [np.array(Image.open(f).convert('L'), dtype=np.float32) for f in files]
    print(f'\n=== {name} ({len(imgs)} frames @ {fps}fps) ===')
    print(f'{"Time":>6} | {"MeanDiff":>8} | {"Status":>10}')
    print('-' * 50)
    last_motion = 0
    for i in range(1, len(imgs)):
        diff = float(np.mean(np.abs(imgs[i] - imgs[i-1])))
        t = i / fps
        status = 'FROZEN' if diff < 1.0 else ('LOW' if diff < 3.0 else 'moving')
        if diff > 0.5:
            last_motion = t
        bar = '#' * int(min(diff, 60))
        print(f'{t:5.2f}s | {diff:7.2f}  | {status:>7} | {bar}')
    print(f'\nLast motion at: {last_motion:.2f}s (out of {(len(imgs)-1)/fps:.2f}s video)')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'A1'
    video = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs') / f'{target}_cyberpunk_768p.mp4'
    if len(sys.argv) > 2:
        video = Path(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 else target
    extract(video, name)
    analyze(name)