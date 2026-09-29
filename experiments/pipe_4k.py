"""4K pipeline - tight memory, smaller tiles, float16 accumulation."""
import sys, os, time, shutil
import torch, numpy as np, subprocess
from pathlib import Path
from PIL import Image
from basicsr.archs.rrdbnet_arch import RRDBNet

if len(sys.argv) < 3:
    print('Usage: pipe_4k.py <input.mp4> <output.mp4>')
    sys.exit(1)

INPUT_VIDEO = Path(sys.argv[1])
OUTPUT_VIDEO = Path(sys.argv[2])
TMP = Path(sys.argv[3]) if len(sys.argv) > 3 else r'E:\Minimax-H3\work_frames\fp_4k'
TILE_SIZE = 256
TILE_OVERLAP = 16
SCALE = 2

IN = TMP / 'in'; UP = TMP / 'up'
IN.mkdir(parents=True, exist_ok=True); UP.mkdir(parents=True, exist_ok=True)
for d in [IN, UP]:
    for f in d.glob('*.png'): f.unlink()

print(f'=== {INPUT_VIDEO.name} -> 4K ===')

print('extracting...')
subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(INPUT_VIDEO),'-vsync','0','-r','24',str(IN/'frame_%04d.png')], check=True)
frames = sorted(IN.glob('*.png'))
for i, f in enumerate(frames):
    tgt = IN / f'frame_{i:04d}.png'
    if str(f) != str(tgt): f.rename(tgt)
frames = sorted(IN.glob('*.png'))
print(f'  {len(frames)} frames')

print('loading model...')
# RRDBNet(num_in_ch, num_out_ch, scale, num_feat, num_block, num_grow_ch)
model = RRDBNet(num_in_ch=3, num_out_ch=3, scale=SCALE, num_feat=64, num_block=23, num_grow_ch=32)
sd = torch.load(r'E:\ComfyUI\models\upscale_models\RealESRGAN_x2plus.pth', map_location='cpu', weights_only=False)
if 'params_ema' in sd: sd = sd['params_ema']
model.load_state_dict(sd, strict=True)
model.eval().cuda()

print(f'upscaling {len(frames)} frames (TILE={TILE_SIZE}, SCALE={SCALE})...')
t0 = time.time()
for idx, fp in enumerate(frames):
    img = Image.open(fp).convert('RGB')
    in_w, in_h = img.size
    out_w, out_h = in_w * SCALE, in_h * SCALE
    if idx == 0:
        print(f'  {in_w}x{in_h} -> {out_w}x{out_h}, peak mem per tile: {TILE_SIZE*2}x{TILE_SIZE*2}x3 float32 = {TILE_SIZE*2*TILE_SIZE*2*3*4/1024/1024:.1f} MB')
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
        if ph or pw: tile = np.pad(tile, ((0,ph),(0,pw),(0,0)), mode='reflect')
        t = torch.from_numpy(np.ascontiguousarray(tile)).permute(2,0,1).float() / 255.0
        tensors.append(t)
    batched = torch.stack(tensors).cuda()
    with torch.no_grad():
        outs = model(batched)
    outs = outs.clamp(0, 1).cpu().numpy()
    # Use float16 for canvas (saves ~50% memory)
    canvas = np.zeros((out_h, out_w, 3), dtype=np.float16)
    weight = np.zeros((out_h, out_w, 1), dtype=np.float16)
    for tile_out, (ox, oy), (oh, ow) in zip(outs, coords, orig_sizes):
        tile_out = tile_out.transpose(1, 2, 0).astype(np.float16)
        canvas[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += tile_out[:oh*SCALE, :ow*SCALE]
        weight[oy*SCALE:oy*SCALE + oh*SCALE, ox*SCALE:ox*SCALE + ow*SCALE] += 1
    # Free memory before final conversion
    del outs, batched, tensors, tiles
    import gc; gc.collect()
    torch.cuda.empty_cache()
    canvas = canvas.astype(np.float32) / np.maximum(weight.astype(np.float32), 1e-6)
    canvas = (canvas * 255.0).clip(0, 255).astype(np.uint8)
    Image.fromarray(canvas).save(UP / fp.name)
    del canvas, weight; gc.collect()
    if idx % 5 == 0:
        el = time.time() - t0
        eta = el / max(idx+1, 1) * (len(frames) - idx - 1)
        print(f'  [{idx+1}/{len(frames)}] {el:.0f}s ETA {eta:.0f}s')
print(f'done in {time.time()-t0:.1f}s')

print('combining...')
subprocess.run([
    'ffmpeg','-y','-loglevel','error',
    '-framerate','24','-i',str(UP/'frame_%04d.png'),
    '-i',str(INPUT_VIDEO),
    '-map','0:v:0','-map','1:a:0',
    '-c:v','libx264','-pix_fmt','yuv420p',
    '-crf','20','-c:a','aac','-b:a','128k',
    str(OUTPUT_VIDEO)
], check=True)
print(f'saved: {OUTPUT_VIDEO}')