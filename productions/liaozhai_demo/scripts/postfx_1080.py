"""Final 1080p encode with anime post-FX: lanczos downscale -> CAS sharpen
-> fine temporal grain. Order matters: grain last so it is not sharpened.

Usage: python postfx_1080.py IN.mp4 OUT.mp4 [--cas 0.35] [--grain 2]
"""
import argparse
import subprocess
import sys
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, FFPROBE, prepend_to_path  # noqa: E402
prepend_to_path()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--cas', type=float, default=0.35)
    ap.add_argument('--grain', type=float, default=2.0)
    ap.add_argument('--crf', type=float, default=16)
    args = ap.parse_args()

    wh = subprocess.check_output(
        [FFPROBE, '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,avg_frame_rate', '-of',
         'csv=p=0', args.input]).decode().strip().split(',')
    w, h = int(wh[0]), int(wh[1])
    vf = []
    if (w, h) != (1920, 1080):
        vf.append('scale=1920:1080:flags=lanczos')
    vf.append(f'cas={args.cas}')
    vf.append(f'noise=alls={args.grain}:allf=t+u')
    print('vf:', ','.join(vf))

    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-i', args.input,
           '-vf', ','.join(vf),
           '-c:v', 'libx264', '-preset', 'slow', '-crf', str(args.crf),
           '-bf', '2', '-pix_fmt', 'yuv420p',
           '-c:a', 'copy', args.output]
    subprocess.run(cmd, check=True)
    out = Path(args.output)
    print(f'done: {out} ({out.stat().st_size/1e6:.1f}MB)')


if __name__ == '__main__':
    main()
