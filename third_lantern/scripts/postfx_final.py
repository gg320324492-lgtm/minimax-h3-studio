"""Final master finishing: crop to 16:9, lanczos resize, CAS, fine grain.

Works from the FlashVSR 2688x1536 intermediate (1.75:1) -> exact 2560x1440 or
1920x1080. Grain last so it is not sharpened.

Usage: python postfx_final.py IN OUT [--w 2560] [--h 1440] [--cas 0.3] [--grain 1.5]
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
    ap.add_argument('--w', type=int, default=2560)
    ap.add_argument('--h', type=int, default=1440)
    ap.add_argument('--cas', type=float, default=0.3)
    ap.add_argument('--grain', type=float, default=1.5)
    ap.add_argument('--crf', type=float, default=16)
    args = ap.parse_args()

    wh = subprocess.check_output(
        [FFPROBE, '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
         args.input]).decode().strip().split(',')
    w, h = int(wh[0]), int(wh[1])
    vf = []
    # crop source height to the 16:9 window (centered) when source is taller AR
    target_ar = args.w / args.h
    src_ar = w / h
    if abs(src_ar - target_ar) > 0.005:
        crop_h = int(w / target_ar) // 2 * 2
        if crop_h < h:
            vf.append(f'crop={w}:{crop_h}:{(w - w) // 2}:{(h - crop_h) // 2}')
    vf.append(f'scale={args.w}:{args.h}:flags=lanczos')
    vf.append(f'cas={args.cas}')
    vf.append(f'noise=alls={args.grain}:allf=t+u')
    print('vf:', ','.join(vf))

    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-i', args.input,
           '-vf', ','.join(vf),
           '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', str(max(17, args.crf + 3)),
           '-b:v', '0', '-pix_fmt', 'yuv420p',
           '-an', args.output]
    subprocess.run(cmd, check=True)
    out = Path(args.output)
    print(f'done: {out} ({out.stat().st_size/1e6:.1f}MB)')


if __name__ == '__main__':
    main()
