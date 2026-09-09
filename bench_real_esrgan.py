"""Real-ESRGAN multi-config benchmark: tile size × overlap × scale variations."""
import sys, time, gc, shutil, subprocess
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

SRC = Path(r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\A1_cyberpunk_768p.mp4')
OUT = Path(r'E:\Minimax-H3\bench_real_esrgan')
TMP = Path(r'E:\Minimax-H3\work_frames\bench_real_esrgan')
MODEL = Path(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth')

def extract(src, dest, fps=24):
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob('*.png'): f.unlink()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(src), '-vsync', '0', '-r', str(fps),
        str(dest / 'frame_%04d.png')
    ], check=True)
    frames = sorted(dest.glob('*.png'))
    for i, f in enumerate(frames):
        tgt = dest / f'frame_{i:04d}.png'
        if str(f) != str(tgt): f.rename(tgt)
    return sorted(dest.glob('*.png'))

def upscale(src_dir, dst_dir, tile_size, overlap, scale):
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
        cur_mem = torch.cuda.max_memory_allocated() / 1024**3
        peak_mem = max(peak_mem, cur_mem)
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

def combine(frames_dir, audio_src, output, fps=24):
    fixed = frames_dir.parent / f'{frames_dir.name}_fixed'
    fixed.mkdir(exist_ok=True)
    for f in fixed.glob('*.png'): f.unlink()
    for i, f in enumerate(sorted(frames_dir.glob('*.png'))):
        shutil.copy(str(f), str(fixed / f'frame_{i:04d}.png'))
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', str(fps), '-i', str(fixed / 'frame_%04d.png'),
        '-i', str(audio_src),
        '-map', '0:v:0', '-map', '1:a:0?',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-crf', '18', '-c:a', 'aac', '-b:a', '128k',
        str(output)
    ], check=True)

def bench(label, tile, overlap, scale):
    print(f'\n=== {label} (tile={tile}, overlap={overlap}, scale={scale}) ===')
    frames_dir = TMP / 'frames'
    src_frames = extract(SRC, frames_dir)
    print(f'  frames: {len(src_frames)} @ {Image.open(src_frames[0]).size}')

    up_dir = TMP / f'up_{label}'
    t_up, peak, (ow, oh) = upscale(frames_dir, up_dir, tile, overlap, scale)
    print(f'  upscale: {t_up:.1f}s, peak VRAM={peak:.2f}GB, out={ow}x{oh}')

    out_mp4 = OUT / f'{label}.mp4'
    combine(up_dir, SRC, out_mp4)
    sz_mb = out_mp4.stat().st_size / 1e6
    print(f'  mp4: {out_mp4.name} ({sz_mb:.1f}MB)')

    # Cleanup tmp dirs
    for f in frames_dir.glob('*.png'): f.unlink()
    for f in up_dir.glob('*.png'): f.unlink()
    fixed = TMP / f'{up_dir.name}_fixed'
    for f in fixed.glob('*.png'): f.unlink()
    return {'label': label, 'tile': tile, 'overlap': overlap, 'scale': scale,
            'time_s': round(t_up, 1), 'peak_vram_gb': round(peak, 2),
            'out_res': f'{ow}x{oh}', 'mp4_mb': round(sz_mb, 1)}

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    # Test variants
    results = []
    results.append(bench('256_16_2x', 256, 16, 2))
    results.append(bench('384_32_2x', 384, 32, 2))
    results.append(bench('512_32_2x', 512, 32, 2))
    results.append(bench('256_32_2x', 256, 32, 2))

    print('\n\n=== BENCHMARK SUMMARY ===')
    print(f"{'Label':<20} {'tile':<6} {'ovr':<5} {'scale':<6} {'time':<8} {'VRAM':<8} {'res':<12} {'size':<8}")
    for r in results:
        print(f"{r['label']:<20} {r['tile']:<6} {r['overlap']:<5} {r['scale']:<6} {r['time_s']:<8} {r['peak_vram_gb']:<8} {r['out_res']:<12} {r['mp4_mb']:<8}")