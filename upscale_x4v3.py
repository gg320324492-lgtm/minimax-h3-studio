"""Single-pass 4x upscale with realesr-general-x4v3 (SRVGGNetCompact, fp16).

Comparison candidate for pipe_fast.py + pipe_4k_fast.py chained 2x+2x.
Usage: upscale_x4v3.py <input.mp4> <output.mp4> [tile=512] [overlap=32]
"""
import sys, gc, time
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image
from basicsr.archs.srvgg_arch import SRVGGNetCompact

if len(sys.argv) < 3:
    print('Usage: upscale_x4v3.py <input.mp4> <output.mp4> [tile=512] [overlap=32]')
    sys.exit(1)

INPUT_VIDEO = Path(sys.argv[1])
OUTPUT_VIDEO = Path(sys.argv[2])
TILE_SIZE = int(sys.argv[3]) if len(sys.argv) > 3 else 512
TILE_OVERLAP = int(sys.argv[4]) if len(sys.argv) > 4 else 32
TMP_BASE = Path(sys.argv[5]) if len(sys.argv) > 5 else Path(r'E:\Minimax-H3\work_frames\x4v3')

FRAMES_DIR = TMP_BASE / 'in'
UPSCALED_DIR = TMP_BASE / 'up'


def main():
    for d in [FRAMES_DIR, UPSCALED_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob('*.png'): f.unlink()

    print(f'=== {INPUT_VIDEO.name} -> {OUTPUT_VIDEO.name} (x4v3 TILE={TILE_SIZE} OV={TILE_OVERLAP} fp16) ===')

    t0 = time.time()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(INPUT_VIDEO), '-vsync', '0', '-r', '24',
        str(FRAMES_DIR / 'frame_%04d.png')
    ], check=True)
    frames = sorted(FRAMES_DIR.glob('*.png'))
    for i, f in enumerate(frames):
        tgt = FRAMES_DIR / f'frame_{i:04d}.png'
        if str(f) != str(tgt): f.rename(tgt)
    frames = sorted(FRAMES_DIR.glob('*.png'))
    print(f'[1/3] extracted {len(frames)} frames in {time.time()-t0:.1f}s')

    t0 = time.time()
    model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64,
                            num_conv=32, upscale=4, act_type='prelu')
    sd = torch.load(r'E:\ComfyUI\models\upscale_models\realesr-general-x4v3.pth',
                    map_location='cpu', weights_only=False)
    if 'params_ema' in sd: sd = sd['params_ema']
    elif 'params' in sd: sd = sd['params']
    model.load_state_dict(sd, strict=True)
    model.eval().cuda().half()
    print(f'[2/3] model loaded (x4v3 fp16), upscaling 4x single pass...')

    out_w = out_h = None
    for idx, fp in enumerate(frames):
        img = Image.open(fp).convert('RGB')
        in_w, in_h = img.size
        if out_w is None:
            out_w, out_h = in_w * 4, in_h * 4
            print(f'  in {in_w}x{in_h} -> out {out_w}x{out_h}')
        tiles = []; coords = []
        for y in range(0, in_h, TILE_SIZE - TILE_OVERLAP):
            for x in range(0, in_w, TILE_SIZE - TILE_OVERLAP):
                xe = min(x + TILE_SIZE, in_w); ye = min(y + TILE_SIZE, in_h)
                tiles.append(np.asarray(img.crop((x, y, xe, ye))))
                coords.append((x, y))
        tensors = []; orig_sizes = []
        for tile in tiles:
            h, w, _ = tile.shape
            orig_sizes.append((h, w))
            ph = TILE_SIZE - h; pw = TILE_SIZE - w
            if ph or pw:
                tile = np.pad(tile, ((0, ph), (0, pw), (0, 0)), mode='reflect')
            t = torch.from_numpy(np.ascontiguousarray(tile)).permute(2, 0, 1).float() / 255.0
            tensors.append(t)
        batched = torch.stack(tensors).cuda().half()
        with torch.no_grad():
            outs = model(batched)
        outs = outs.clamp(0, 1).cpu().float().numpy()
        canvas = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
        for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
            tile_out = tile_out.transpose(1, 2, 0)
            canvas[oy*4:oy*4 + oh*4, ox*4:ox*4 + ow*4] += tile_out[:oh*4, :ow*4]
            weight[oy*4:oy*4 + oh*4, ox*4:ox*4 + ow*4] += 1
        canvas = canvas / np.maximum(weight, 1e-6)
        canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(canvas).save(UPSCALED_DIR / fp.name)
        del canvas, weight, outs, batched, tensors, tiles
        if idx % 20 == 0:
            gc.collect(); torch.cuda.empty_cache()
        if idx % 10 == 0:
            elapsed = time.time() - t0
            eta = elapsed / max(idx+1, 1) * (len(frames) - idx - 1)
            print(f'  [{idx+1}/{len(frames)}] {elapsed:.0f}s ETA {eta:.0f}s')
    print(f'[2/3] done in {time.time()-t0:.1f}s')

    t0 = time.time()
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', '24',
        '-i', str(UPSCALED_DIR / 'frame_%04d.png'),
        '-i', str(INPUT_VIDEO),
        '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-crf', '18', '-c:a', 'aac', '-b:a', '128k',
        str(OUTPUT_VIDEO)
    ], check=True)
    print(f'[3/3] combined in {time.time()-t0:.1f}s')
    print(f'  saved: {OUTPUT_VIDEO}')

if __name__ == '__main__':
    main()
