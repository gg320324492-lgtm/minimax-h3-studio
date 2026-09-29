"""Upscale A1 video frames from 1344x768 to 2688x1536 (2K) via Real-ESRGAN.

Uses tile-based inference to avoid OOM on 32GB.
"""
import sys
import torch
import numpy as np
import subprocess
import shutil
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

INPUT_VIDEO = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A2_mountain_768p.mp4')
OUTPUT_VIDEO = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\B2_mountain_2K.mp4')
FRAMES_DIR = Path(r'E:\MiniMax-H3\upscale_frames')
UPSCALED_DIR = Path(r'E:\MiniMax-H3\upscale_frames_2k')

TILE_SIZE = 384     # tile edge in input pixels (before 2x upscale)
TILE_OVERLAP = 32   # overlap to avoid seams
SCALE = 2
BATCH_FRAMES = 4    # process N frames at once on GPU

def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    UPSCALED_DIR.mkdir(parents=True, exist_ok=True)
    # Clear old frames
    for f in FRAMES_DIR.glob('*.png'): f.unlink()
    for f in UPSCALED_DIR.glob('*.png'): f.unlink()

    # 1) Extract frames
    print(f'[1/4] Extracting frames from {INPUT_VIDEO.name}...')
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-i', str(INPUT_VIDEO),
        '-vsync', '0', '-frame_pts', '1',
        str(FRAMES_DIR / 'frame_%04d.png')
    ], check=True)
    frames = sorted(FRAMES_DIR.glob('*.png'))
    print(f'  extracted {len(frames)} frames')

    # 2) Load model
    print('[2/4] Loading Real-ESRGAN...')
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=SCALE)
    sd = torch.load(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth',
                    map_location='cpu', weights_only=False)
    if 'params_ema' in sd: sd = sd['params_ema']
    model.load_state_dict(sd, strict=True)
    model.eval().cuda()
    print(f'  model loaded; tiling at {TILE_SIZE}px input / {TILE_SIZE*SCALE}px output')

    # 3) Upscale tile-by-tile, frame-by-frame
    print(f'[3/4] Upscaling {len(frames)} frames...')
    import time
    t0 = time.time()
    out_w = out_h = None
    for idx, fp in enumerate(frames):
        img = Image.open(fp).convert('RGB')
        in_w, in_h = img.size
        if out_w is None:
            out_w, out_h = in_w * SCALE, in_h * SCALE
            print(f'  input: {in_w}x{in_h}, output: {out_w}x{out_h}')
        # Build tile grid
        tiles = []
        coords = []  # (x_in, y_in)
        for y in range(0, in_h, TILE_SIZE - TILE_OVERLAP):
            for x in range(0, in_w, TILE_SIZE - TILE_OVERLAP):
                xe = min(x + TILE_SIZE, in_w)
                ye = min(y + TILE_SIZE, in_h)
                tiles.append(np.asarray(img.crop((x, y, xe, ye))))
                coords.append((x, y))
        # Pad last tile to multiple of SCALE for the model
        tensors = []
        orig_sizes = []  # (orig_h, orig_w) in input pixels
        for tile in tiles:
            h, w, _ = tile.shape
            orig_sizes.append((h, w))
            # Always pad to TILE_SIZE so batched tensors all match
            pad_h = TILE_SIZE - h
            pad_w = TILE_SIZE - w
            if pad_h or pad_w:
                tile = np.pad(tile, ((0, pad_h), (0, pad_w), (0, 0)), mode='reflect')
            t = torch.from_numpy(np.ascontiguousarray(tile)).permute(2, 0, 1).float() / 255.0
            tensors.append(t)
        batched = torch.stack(tensors).cuda()  # [N, 3, TILE_SIZE, TILE_SIZE]

        with torch.no_grad():
            outs = model(batched)  # [N, 3, H*2, W*2]
        outs = outs.clamp(0, 1).cpu().numpy()

        # Stitch tiles
        canvas = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
        for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
            # tile_out is [3, H*2, W*2] - transpose to [H*2, W*2, 3]
            tile_out = tile_out.transpose(1, 2, 0)
            canvas[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += tile_out[:oh*SCALE, :ow*SCALE]
            weight[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += 1
        canvas = canvas / np.maximum(weight, 1e-6)
        canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(canvas).save(UPSCALED_DIR / fp.name)
        if idx % 10 == 0:
            elapsed = time.time() - t0
            eta = elapsed / max(idx + 1, 1) * (len(frames) - idx - 1)
            print(f'  [{idx+1}/{len(frames)}] {elapsed:.1f}s elapsed, ETA {eta:.0f}s')
    total = time.time() - t0
    print(f'  upscaling done in {total:.1f}s ({total/len(frames):.2f}s/frame)')

    # 4) Combine with original audio
    print('[4/4] Combining frames + original audio into video...')
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', '24', '-i', str(UPSCALED_DIR / 'frame_%04d.png'),
        '-i', str(INPUT_VIDEO),
        '-map', '0:v:0', '-map', '1:a:0?', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-crf', '18', '-c:a', 'copy', '-shortest',
        str(OUTPUT_VIDEO)
    ], check=True)
    print(f'  saved: {OUTPUT_VIDEO}')

if __name__ == '__main__':
    main()