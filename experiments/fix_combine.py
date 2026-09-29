"""Final fixed combine: no -shortest, re-encode audio."""
import sys
import subprocess
import time
from pathlib import Path
import shutil

if len(sys.argv) < 3:
    print('Usage: fix_combine.py <frames_dir> <audio_src.mp4> <output.mp4>')
    sys.exit(1)

FRAMES_DIR = Path(sys.argv[1])
AUDIO_SRC = Path(sys.argv[2])
OUTPUT = Path(sys.argv[3])

frames = sorted(FRAMES_DIR.glob('*.png'))
print(f'frames: {len(frames)} (first={frames[0].name}, last={frames[-1].name})')

# Make sure frames are 0-indexed for image2 demuxer
fixed_dir = FRAMES_DIR.parent / 'fixed_0indexed'
fixed_dir.mkdir(exist_ok=True)
for f in fixed_dir.glob('*.png'): f.unlink()
for i, f in enumerate(frames):
    shutil.copy(str(f), str(fixed_dir / f'frame_{i:04d}.png'))
print(f'prepared {len(frames)} frames 0-indexed in {fixed_dir}')

t0 = time.time()
r = subprocess.run([
    'ffmpeg', '-y', '-loglevel', 'error',
    '-framerate', '24',
    '-i', str(fixed_dir / 'frame_%04d.png'),
    '-i', str(AUDIO_SRC),
    '-map', '0:v:0', '-map', '1:a:0',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
    '-crf', '18', '-c:a', 'aac', '-b:a', '128k',
    str(OUTPUT)
], capture_output=True)
if r.returncode != 0:
    print('FAIL:', r.stderr.decode()[:500])
    sys.exit(1)
print(f'done in {time.time()-t0:.1f}s: {OUTPUT}')