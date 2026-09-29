"""Compute frame consistency metrics for upscaled videos.
- Per-frame sharpness (Laplacian variance)
- Inter-frame consistency (temporal flicker)
- Compare across pipelines."""
import sys
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

VIDEOS = [
    ('A1_baseline_768p', r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4'),
    ('B1_esrgan_2K', r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\B1_cyberpunk_2K.mp4'),
    ('C1_esrgan_4K', r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\C1_cyberpunk_4K.mp4'),
    ('Lulu_10s_768p', r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\Lulu_10s_768p.mp4'),
]

TMP = Path(r'E:\Minimax-H3\work_frames\flicker_test')

def extract(video, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob('*.png'): f.unlink()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(video), '-vsync', '0',   # no -r: never resample the frame rate
        str(out_dir / 'frame_%04d.png')
    ], check=True)
    return sorted(out_dir.glob('*.png'))

def analyze(frames):
    """Return dict of metrics."""
    sharpness = []
    diffs = []
    laplacian_var = []
    prev = None
    for i, fp in enumerate(frames):
        img = np.array(Image.open(fp).convert('L'))  # grayscale
        # Sharpness via Laplacian
        lap = cv2.Laplacian(img, cv2.CV_64F)
        v = lap.var()
        laplacian_var.append(v)
        sharpness.append(img.std())
        if prev is not None:
            d = np.abs(img.astype(np.float32) - prev.astype(np.float32)).mean()
            diffs.append(d)
        prev = img
    return {
        'n_frames': len(frames),
        'avg_laplacian': np.mean(laplacian_var),
        'median_laplacian': np.median(laplacian_var),
        'avg_sharpness': np.mean(sharpness),
        'avg_interframe_diff': np.mean(diffs) if diffs else 0,
        'max_interframe_diff': np.max(diffs) if diffs else 0,
        'std_interframe_diff': np.std(diffs) if diffs else 0,
    }

def main():
    results = []
    for name, video in VIDEOS:
        print(f'\n=== {name} ===')
        v = Path(video)
        if not v.exists():
            print(f'  NOT FOUND: {v}')
            continue
        print(f'  size: {v.stat().st_size/1e6:.1f}MB')
        frames = extract(v, TMP / name)
        if not frames:
            print(f'  no frames extracted!')
            continue
        m = analyze(frames)
        m['name'] = name
        results.append(m)
        print(f'  frames: {m["n_frames"]}')
        print(f'  avg laplacian (sharpness): {m["avg_laplacian"]:.1f}')
        print(f'  avg inter-frame diff: {m["avg_interframe_diff"]:.2f}')
        print(f'  max inter-frame diff: {m["max_interframe_diff"]:.2f}')

    print('\n\n=== METRICS SUMMARY ===')
    print(f"{'name':<25} {'frames':<8} {'avg_lap':<12} {'avg_diff':<12} {'max_diff':<12}")
    for r in results:
        print(f"{r['name']:<25} {r['n_frames']:<8} {r['avg_laplacian']:<12.1f} {r['avg_interframe_diff']:<12.2f} {r['max_interframe_diff']:<12.2f}")

if __name__ == '__main__':
    main()