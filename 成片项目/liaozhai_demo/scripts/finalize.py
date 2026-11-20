"""Finalize liaozhai_demo: copy deliverables into 09_final + a crf26 small
distribution copy + cover frame."""
import subprocess
import sys
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
SRC = PROJECT / '07_edit' / 'LZ_WITH_SUBTITLES.mp4'
OUT = PROJECT / '09_final'
NAME = '灯下无影_演示版_1080P.mp4'


def main():
    if not SRC.exists():
        print(f'ERROR: {SRC} not found')
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / NAME
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(SRC), '-c', 'copy',
                    str(dst)], check=True)
    small = OUT / '灯下无影_演示版_分发版_crf26.mp4'
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(SRC),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '26',
                    '-c:a', 'aac', '-b:a', '160k', '-pix_fmt', 'yuv420p',
                    str(small)], check=True)
    cover = OUT / 'cover.png'
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', '28', '-i', str(dst),
                    '-frames:v', '1', str(cover)], check=True)
    print(f'final:  {dst} ({dst.stat().st_size/1e6:.1f}MB)')
    print(f'small:  {small} ({small.stat().st_size/1e6:.1f}MB)')
    print(f'cover:  {cover}')


if __name__ == '__main__':
    main()
