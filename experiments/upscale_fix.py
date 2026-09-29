"""Fixed version: use `-r 24` (not -framerate 24) for image2 demuxer."""
import sys
import torch
import numpy as np
import subprocess
import time
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

if len(sys.argv) < 3:
    print('Usage: upscale_fix.py <input.mp4> <output.mp4>')
    sys.exit(1)

INPUT_VIDEO = Path(sys.argv[1])
OUTPUT_VIDEO = Path(sys.argv[2])
TMP_BASE = Path(sys.argv[3]) if len(sys.argv) > 3 else r'E:\Minimax-H3\work_frames\upscale_fix'
FRAMES_DIR = TMP_BASE / 'in'
UPSCALED_DIR = TMP_BASE / 'out'
TILE_SIZE = 384
TILE_OVERLAP = 32
SCALE = 2

def main():
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    UPSCALED_DIR.mkdir(parents=True, exist_ok=True)
    for d in [FRAMES_DIR, UPSCALED_DIR]:
        for f in d.glob('*.png'): f.unlink()

    print(f'[1/4] Extracting ALL frames from {INPUT_VIDEO.name}')
    # Use -vsync 0 to keep all frames, force 24fps interpretation
    r = subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(INPUT_VIDEO),
        '-vsync', '0', '-r', '24',
        str(FRAMES_DIR / 'frame_%04d.png')
    ], capture_output=True)
    if r.returncode != 0:
        print('FFMPEG STDERR:', r.stderr.decode())
        sys.exit(1)
    frames = sorted(FRAMES_DIR.glob('*.png'))
    print(f'  {len(frames)} frames extracted')

    print('[2/4] Loading Real-ESRGAN...')
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=SCALE)
    sd = torch.load(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth',
                    map_location='cpu', weights_only=False)
    if 'params_ema' in sd: sd = sd['params_ema']
    model.load_state_dict(sd, strict=True)
    model.eval().cuda()

    print(f'[3/4] Upscaling {len(frames)} frames...')
    t0 = time.time()
    out_w = out_h = None
    for idx, fp in enumerate(frames):
        img = Image.open(fp).convert('RGB')
        in_w, in_h = img.size
        if out_w is None:
            out_w, out_h = in_w * SCALE, in_h * SCALE
            print(f'  in {in_w}x{in_h} -> out {out_w}x{out_h}')
        tiles = []
        coords = []
        for y in range(0, in_h, TILE_SIZE - TILE_OVERLAP):
            for x in range(0, in_w, TILE_SIZE - TILE_OVERLAP):
                xe = min(x + TILE_SIZE, in_w); ye = min(y + TILE_SIZE, in_h)
                tiles.append(np.asarray(img.crop((x, y, xe, ye))))
                coords.append((x, y))
        tensors = []
        orig_sizes = []
        for tile in tiles:
            h, w, _ = tile.shape
            orig_sizes.append((h, w))
            ph = TILE_SIZE - h; pw = TILE_SIZE - w
            if ph or pw:
                tile = np.pad(tile, ((0, ph), (0, pw), (0, 0)), mode='reflect')
            t = torch.from_numpy(np.ascontiguousarray(tile)).permute(2, 0, 1).float() / 255.0
            tensors.append(t)
        batched = torch.stack(tensors).cuda()
        with torch.no_grad():
            outs = model(batched)
        outs = outs.clamp(0, 1).cpu().numpy()
        canvas = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
        for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
            tile_out = tile_out.transpose(1, 2, 0)
            canvas[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += tile_out[:oh*SCALE, :ow*SCALE]
            weight[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += 1
        canvas = canvas / np.maximum(weight, 1e-6)
        canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(canvas).save(UPSCALED_DIR / fp.name)
        if idx % 20 == 0:
            elapsed = time.time() - t0
            eta = elapsed / max(idx + 1, 1) * (len(frames) - idx - 1)
            print(f'  [{idx+1}/{len(frames)}] {elapsed:.0f}s, ETA {eta:.0f}s')
    total = time.time() - t0
    print(f'  done in {total:.1f}s')

    print('[4/4] Combining...')
    # KEY: rename frames to 0-indexed for ffmpeg image2 demuxer
    combined_dir = TMP_BASE / 'combined'
    combined_dir.mkdir(parents=True, exist_ok=True)
    for f in combined_dir.glob('*.png'): f.unlink()
    for i, f in enumerate(sorted(UPSCALED_DIR.glob('*.png'))):
        # Use shutil to avoid cross-fs rename issues
        import shutil
        shutil.copy(str(f), str(combined_dir / f'frame_{i:04d}.png'))
    # Use -framerate input option (sets demuxer framerate)
    r = subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', '24',
        '-i', str(combined_dir / 'frame_%04d.png'),
        '-i', str(INPUT_VIDEO),
        '-map', '0:v:0', '-map', '1:a:0?', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-crf', '18', '-c:a', 'copy', '-shortest', str(OUTPUT_VIDEO)
    ], capture_output=True)
    if r.returncode != 0:
        print('FFMPEG STDERR:', r.stderr.decode())
        sys.exit(1)
    print(f'  saved: {OUTPUT_VIDEO}')

if __name__ == '__main__':
    main()