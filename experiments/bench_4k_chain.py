"""Test upscale 2K → 4K vs 768p → 4K (via 2x 4x) on same source."""
import sys, time, gc
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

MODEL = Path(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth')
TMP = Path(r'E:\Minimax-H3\work_frames\bench_4k_chain')
OUT = Path(r'E:\Minimax-H3\bench_4k_chain')

def upscale_dir(src_dir, dst_dir, tile_size=384, overlap=32, scale=2):
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in dst_dir.glob('*.png'): f.unlink()
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=scale)
    sd = torch.load(str(MODEL), map_location='cpu', weights_only=False)
    if 'params_ema' in sd: sd = sd['params_ema']
    model.load_state_dict(sd, strict=True)
    model.eval().cuda()

    frames = sorted(src_dir.glob('*.png'))
    out_w = out_h = None
    t0 = time.time()
    peak_mem = 0
    for idx, fp in enumerate(frames):
        img = Image.open(fp).convert('RGB')
        in_w, in_h = img.size
        if out_w is None:
            out_w, out_h = in_w * scale, in_h * scale
        tiles = []; coords = []
        for y in range(0, in_h, tile_size - overlap):
            for x in range(0, in_w, tile_size - overlap):
                xe = min(x + tile_size, in_w); ye = min(y + tile_size, in_h)
                tiles.append(np.asarray(img.crop((x, y, xe, ye))))
                coords.append((x, y))
        tensors = []; orig_sizes = []
        for tile in tiles:
            h, w, _ = tile.shape
            orig_sizes.append((h, w))
            ph = tile_size - h; pw = tile_size - w
            if ph or pw:
                tile = np.pad(tile, ((0,ph),(0,pw),(0,0)), mode='reflect')
            t = torch.from_numpy(np.ascontiguousarray(tile)).permute(2,0,1).float() / 255.0
            tensors.append(t)
        batched = torch.stack(tensors).cuda()
        with torch.no_grad():
            outs = model(batched)
        peak_mem = max(peak_mem, torch.cuda.max_memory_allocated() / 1024**3)
        outs = outs.clamp(0, 1).cpu().numpy()
        canvas = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
        for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
            tile_out = tile_out.transpose(1, 2, 0)
            canvas[oy*scale:oy*scale + oh*scale, ox*scale:ox*scale + ow*scale] += tile_out[:oh*scale, :ow*scale]
            weight[oy*scale:oy*scale + oh*scale, ox*scale:ox*scale + ow*scale] += 1
        canvas = canvas / np.maximum(weight, 1e-6)
        canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(canvas).save(dst_dir / fp.name)
        del canvas, weight, outs, batched, tensors, tiles
        gc.collect(); torch.cuda.empty_cache()
    return time.time() - t0, peak_mem, (out_w, out_h)

def extract(video, out_dir, fps=24):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob('*.png'): f.unlink()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(video), '-vsync', '0', '-r', str(fps),
        str(out_dir / 'frame_%04d.png')
    ], check=True)
    frames = sorted(out_dir.glob('*.png'))
    for i, f in enumerate(frames):
        tgt = out_dir / f'frame_{i:04d}.png'
        if str(f) != str(tgt): f.rename(tgt)
    return sorted(out_dir.glob('*.png'))

# Test A: 768p → 4K (2x 2x chain) using already-existing frames
print('=== A: 768p → 2K → 4K (chain) ===')
A1 = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4')
B1_2k = TMP / 'B1_2k'; B1_4k = TMP / 'B1_4k'
print('  extracting A1...')
A1_frames = extract(A1, TMP / 'A1_768p')
print(f'  A1 frames: {len(A1_frames)}')

t1, m1, sz1 = upscale_dir(TMP / 'A1_768p', B1_2k)
print(f'  pass 1 (768p → 2K): {t1:.1f}s, {sz1[0]}x{sz1[1]}, peak {m1:.2f}GB')

t2, m2, sz2 = upscale_dir(B1_2k, B1_4k)
print(f'  pass 2 (2K → 4K): {t2:.1f}s, {sz2[0]}x{sz2[1]}, peak {m2:.2f}GB')

print(f'  total: {t1+t2:.1f}s')

# Cleanup
for d in [TMP / 'A1_768p', B1_2k, B1_4k]:
    for f in d.glob('*.png'): f.unlink()