"""Comprehensive video quality comparison metrics.
Compares videos by computing:
- Sharpness (Laplacian variance per frame, mean)
- Inter-frame flicker (mean abs diff between consecutive frames)
- Color stability (per-channel mean over frames)
- Perceptual quality (using simple SSIM proxy)
"""
import sys
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

def extract(video, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob('*.png'): f.unlink()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(video), '-vsync', '0',   # no -r: never resample the frame rate
        str(out_dir / 'frame_%04d.png')
    ], check=True)
    return sorted(out_dir.glob('*.png'))


def analyze_video(frames):
    """Per-frame sharpness + inter-frame consistency."""
    sharpness = []
    edge_density = []
    diffs = []
    color_means = []
    prev = None
    for fp in frames:
        img = np.array(Image.open(fp).convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        # Laplacian (sharpness)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness.append(lap.var())
        # Edge density (Canny)
        edges = cv2.Canny(gray, 50, 150)
        edge_density.append(edges.sum() / edges.size)
        # Color mean
        color_means.append(img.mean(axis=(0, 1)))
        # Inter-frame diff
        if prev is not None:
            d = np.abs(gray.astype(np.float32) - prev.astype(np.float32)).mean()
            diffs.append(d)
        prev = gray
    return {
        'n_frames': len(frames),
        'avg_sharpness': np.mean(sharpness),
        'median_sharpness': np.median(sharpness),
        'avg_edge_density': np.mean(edge_density),
        'avg_interframe_diff': np.mean(diffs) if diffs else 0,
        'max_interframe_diff': np.max(diffs) if diffs else 0,
        'std_interframe_diff': np.std(diffs) if diffs else 0,
        'avg_color_R': np.mean([c[0] for c in color_means]),
        'avg_color_G': np.mean([c[1] for c in color_means]),
        'avg_color_B': np.mean([c[2] for c in color_means]),
    }


def ssim_simple(img1, img2):
    """Simple SSIM approximation (luminance + structure)."""
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2
    sigma1_sq = cv2.GaussianBlur(img1 ** 2, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 ** 2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
    num = (2 * mu1_mu2 + c1) * (2 * sigma12 + c2)
    den = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    ssim_map = num / den
    return ssim_map.mean()


def main():
    pairs = [
        # (name, baseline, candidate)
        ('B1_2K_vs_A1_768p',
         r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4',
         r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\B1_cyberpunk_2K.mp4'),
        ('C1_4K_vs_A1_768p',
         r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4',
         r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\C1_cyberpunk_4K.mp4'),
    ]
    TMP = Path(r'E:\Minimax-H3\work_frames\quality_comp')

    for label, base, cand in pairs:
        print(f'\n=== {label} ===')
        base_v = Path(base)
        cand_v = Path(cand)
        if not base_v.exists() or not cand_v.exists():
            print(f'  MISSING')
            continue
        # Get dimensions
        bf = extract(base_v, TMP / f'{label}_base')
        cf = extract(cand_v, TMP / f'{label}_cand')
        print(f'  baseline frames: {len(bf)} @ {Image.open(bf[0]).size}')
        print(f'  candidate frames: {len(cf)} @ {Image.open(cf[0]).size}')

        # Resize baseline to match candidate (for fair comparison)
        base_resized = []
        target_w, target_h = Image.open(cf[0]).size
        for fp in bf:
            img = Image.open(fp).convert('RGB').resize((target_w, target_h), Image.LANCZOS)
            img.save(fp.parent / (fp.stem + '_r.png'))
            base_resized.append(fp.parent / (fp.stem + '_r.png'))

        bm = analyze_video(base_resized)
        cm = analyze_video(cf)
        print(f'  baseline (resized): avg_lap={bm["avg_sharpness"]:.1f}, avg_diff={bm["avg_interframe_diff"]:.2f}')
        print(f'  candidate (4K):     avg_lap={cm["avg_sharpness"]:.1f}, avg_diff={cm["avg_interframe_diff"]:.2f}')

        # SSIM between baseline and candidate (resize base to candidate size)
        # This is unfair since candidate was upscaled FROM baseline
        # Instead compute structural fidelity: SSIM(cand_down, base)
        # Skip if too slow; just use the average diff
        # Sample 5 frames for SSIM
        ssim_scores = []
        sample_idx = np.linspace(0, min(len(bf), len(cf)) - 1, 5, dtype=int)
        for idx in sample_idx:
            base_img = np.array(Image.open(bf[idx]).convert('RGB').resize(
                (Image.open(cf[idx]).size[0], Image.open(cf[idx]).size[1]), Image.LANCZOS))
            cand_img = np.array(Image.open(cf[idx]).convert('RGB'))
            s = ssim_simple(base_img, cand_img)
            ssim_scores.append(s)
        print(f'  SSIM (base→candidate, 5 frames): {np.mean(ssim_scores):.3f} ± {np.std(ssim_scores):.3f}')

        # Cleanup resized
        for fp in base_resized:
            fp.unlink(missing_ok=True)

if __name__ == '__main__':
    main()