"""Finalize third_lantern: 2K master + derived 1080p + crf26 small + cover."""
import subprocess
import sys
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/third_lantern')
SRC = PROJECT / '07_edit' / 'TL_WITH_SUBTITLES.mp4'
OUT = PROJECT / '09_final'
NAME2K = '第三盏灯_演示版_2K.mp4'
NAME1080 = '第三盏灯_演示版_1080P.mp4'


def main():
    if not SRC.exists():
        print(f'ERROR: {SRC} not found')
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)

    dst2k = OUT / NAME2K
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(SRC), '-c', 'copy',
                    str(dst2k)], check=True)

    dst1080 = OUT / NAME1080
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(dst2k),
                    '-vf', 'scale=1920:1080:flags=lanczos,cas=0.2',
                    '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '20', '-b:v', '0',
                    '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
                    str(dst1080)], check=True)

    small = OUT / '第三盏灯_演示版_分发版_crf26.mp4'
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(dst1080),
                    '-c:v', 'h264_nvenc', '-preset', 'p6', '-cq', '28', '-b:v', '0',
                    '-c:a', 'aac', '-b:a', '160k', '-pix_fmt', 'yuv420p',
                    str(small)], check=True)

    cover = OUT / 'cover.png'
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-ss', '47', '-i', str(dst2k),
                    '-frames:v', '1', '-vf', 'scale=1920:-1', str(cover)], check=True)

    for f in (dst2k, dst1080, small):
        print(f'{f.name}: {f.stat().st_size/1e6:.1f}MB')


if __name__ == '__main__':
    main()
