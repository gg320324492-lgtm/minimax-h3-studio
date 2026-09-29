"""Real-ESRGAN test: tile size + batch optimization."""
import sys, time, gc
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

MODEL = Path(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth')
TMP = Path(r'E:\Minimax-H3\work_frames\bench_tile_batch')

def load_model(scale=2, dtype=torch.float32):
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=scale)
    sd = torch.load(str(MODEL), map_location='cpu', weights_only=False)
    if 'params_ema' in sd: sd = sd['params_ema']
    model.load_state_dict(sd, strict=True)
    model.eval().cuda()
    if dtype != torch.float32:
        model = model.to(dtype=dtype)
    return model

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


def upscale_frame(img, model, tile_size, overlap, scale, dtype):
    in_w, in_h = img.size
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
    batched = torch.stack(tensors).cuda().to(dtype)
    with torch.no_grad():
        outs = model(batched)
    outs = outs.clamp(0, 1).cpu().float().numpy()
    canvas = np.zeros((out_h, out_w, 3), dtype=np.float32)
    weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
    for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
        tile_out = tile_out.transpose(1, 2, 0)
        canvas[oy*scale:oy*scale + oh*scale, ox*scale:ox*scale + ow*scale] += tile_out[:oh*scale, :ow*scale]
        weight[oy*scale:oy*scale + oh*scale, ox*scale:ox*scale + ow*scale] += 1
    canvas = canvas / np.maximum(weight, 1e-6)
    canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
    return canvas, out_w, out_h


def bench(label, src_frames, tile, overlap, dtype):
    print(f'\n=== {label} (tile={tile}, overlap={overlap}, dtype={dtype}) ===')
    model = load_model(scale=2, dtype=dtype)
    t0 = time.time()
    peak = 0
    for idx, fp in enumerate(src_frames[:20]):  # only 20 frames for quick test
        img = Image.open(fp).convert('RGB')
        canvas, ow, oh = upscale_frame(img, model, tile, overlap, 2, dtype)
        cur = torch.cuda.max_memory_allocated() / 1024**3
        peak = max(peak, cur)
        del canvas
        gc.collect(); torch.cuda.empty_cache()
    elapsed = time.time() - t0
    fps20 = 20 / elapsed
    fps_full = fps20 * (len(src_frames) / 20)
    print(f'  20 frames in {elapsed:.1f}s = {fps20:.2f} fps')
    print(f'  est full {len(src_frames)} frames: {fps_full:.0f}s')
    print(f'  peak VRAM: {peak:.2f}GB')
    del model
    gc.collect(); torch.cuda.empty_cache()
    return {'label': label, 'tile': tile, 'overlap': overlap, 'dtype': str(dtype).replace('torch.',''),
            'fps': round(fps20, 2), 'peak_vram': round(peak, 2)}


def main():
    A1 = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4')
    frames_dir = TMP / 'A1'
    print('Extracting A1...')
    frames = extract(A1, frames_dir)
    print(f'  {len(frames)} frames')
    results = []
    results.append(bench('256_16_fp32', frames, 256, 16, torch.float32))
    results.append(bench('256_16_fp16', frames, 256, 16, torch.float16))
    results.append(bench('384_32_fp32', frames, 384, 32, torch.float32))
    results.append(bench('384_32_fp16', frames, 384, 32, torch.float16))
    results.append(bench('512_32_fp16', frames, 512, 32, torch.float16))

    print('\n\n=== SUMMARY ===')
    print(f"{'label':<20} {'tile':<6} {'ovr':<4} {'dtype':<8} {'fps':<6} {'VRAM':<6}")
    for r in results:
        print(f"{r['label']:<20} {r['tile']:<6} {r['overlap']:<4} {r['dtype']:<8} {r['fps']:<6} {r['peak_vram']:<6}")

if __name__ == '__main__':
    main()