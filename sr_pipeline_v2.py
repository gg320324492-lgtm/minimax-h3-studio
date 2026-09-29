#!/usr/bin/env python
"""sr_pipeline_v2 -- streaming, fps-faithful, adaptive video super-resolution.

Replaces pipe_fast.py / pipe_4k_fast.py / upscale_x4v3.py / full_pipeline.py.

Defects fixed (all reproduced on this machine, see tests/diag):
  1. FPS-AWARE. v1 hardcoded `-vsync 0 -r 24` on decode and `-framerate 24` on
     encode. Any non-24fps input is silently time-stretched: a 30fps / 2.334s
     clip came back as 2.917s (25% slow motion). v2 probes the exact rational
     frame rate and preserves it end to end.
  2. SILENT-INPUT SAFE. v1 muxed with `-map 1:a:0`; on a video without an audio
     track ffmpeg aborts with "Stream map '1:a:0' matches no streams". Because
     the mux is the LAST step, 54.4s of GPU upscaling was thrown away and no
     output file was produced. v2 uses an optional map and audio modes.
  3. ZERO-DISK STREAMING. v1 wrote a lossless PNG per frame then re-read it
     (a 4K job churned >2GB through disk and left a 38GB work_frames graveyard).
     v2 pipes rawvideo straight through, so intermediate frames never touch disk.
  4. CONTINUOUS BLENDING. v1 averaged overlapping tiles with a box weight, whose
     value steps (1.0 -> 0.5) at the edge of every overlap region, producing a
     luminance step. v2 uses linear ramp weights that sum to exactly 1.0 across
     each overlap, so the weight function is continuous and no pixel is ever
     divided by a small weight.
     MEASURED EFFECT (tests/seam_kernel_ab.py, 300-frame EP01 segment, both at
     tile=512/overlap=32, scored at identical boundaries -- the only variable is
     the kernel): seam gradient energy mean -8.2%, p90 -10.7%, p99 -11.4%;
     worst-case outlier +4.1% (within noise at n=225). So this removes the DC
     step but is NOT "mathematically seamless" -- the ramp is C0, not C1.
     The DOMINANT seam lever is tile/overlap, not the kernel: on the full
     episode, t512/o32 scores seam_mean 1.124 vs 1.473 for t256/o16 (-24%),
     because larger tiles/overlaps make neighbouring tiles see near-identical
     context, so their outputs nearly agree before blending.
  5. fp16 SAFETY. v1 ran `.half()` unguarded. v2 checks each frame for NaN/Inf
     and automatically retries that frame in fp32.
  6. ALLOCATOR DISCIPLINE. pipe_4k_fast.py called gc.collect() +
     torch.cuda.empty_cache() on EVERY frame, which forces a device sync and
     throws away the caching allocator's blocks. v2 clears on a schedule
     (default: never) and only when it actually helps.
  7. Extras: inference_mode, channels_last, cudnn.benchmark, optional
     torch.compile, frame batching, x264/x265/NVENC, colour-tag passthrough,
     even-dimension guard, JSON run report.

Usage:
  python sr_pipeline_v2.py in.mp4 out.mp4 --scale 2 --tile 512 --overlap 32
  python sr_pipeline_v2.py in.mp4 out.mp4 --model x2plus --passes 2   # 2x+2x chain
  python sr_pipeline_v2.py in.mp4 out.mp4 --model x4v3  --scale 4     # single-pass 4x
  python sr_pipeline_v2.py in.mp4 --info                              # probe only
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

# -------------------------------------------------------------------- ffmpeg --
# Binary resolution lives in ffmpeg_env.py -- see that module for why calling a
# bare `ffmpeg` is a trap on this machine (PATH resolves it to Octave's bundled
# 4.2.11, not the 7.1.1 build that ships unused in tools/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_env import FFMPEG, FFMPEG_SOURCE, FFPROBE, version as ffmpeg_version  # noqa: E402


# ---------------------------------------------------------------- model zoo --

COMFY_MODELS = Path(r'E:\ComfyUI\models\upscale_models')

# name -> (arch, ckpt filename, native scale, extra arch kwargs)
MODELS = {
    'x2plus': ('rrdbnet', 'RealESRGAN_x2plus.pth', 2,
               dict(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32)),
    'x4plus': ('rrdbnet', 'RealESRGAN_x4plus.pth', 4,
               dict(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32)),
    'x4v3':   ('srvgg', 'realesr-general-x4v3.pth', 4,
               dict(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, act_type='prelu')),
    # anime-video SRVGG (Real-ESRGAN v0.2.5.0): trained for temporal stability on anime
    'av3':    ('srvgg', 'realesr-animevideov3.pth', 4,
               dict(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, act_type='prelu')),
    # Kim2091 2x-AnimeSharpV4 Fast_RCAN_PU (spandrel arch; fp32 only, CC BY-NC-SA)
    'animev4fast': ('spandrel', '2x-AnimeSharpV4_Fast_RCAN_PU.safetensors', 2, {}),
}


def log(msg: str) -> None:
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


# ------------------------------------------------------------------- probing --

def run_capture(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True)


def probe(path: Path) -> dict:
    """Return everything we need to drive the pipeline correctly."""
    r = run_capture([
        FFPROBE, '-v', 'error', '-print_format', 'json',
        '-show_format', '-show_streams', '-select_streams', 'v:0', str(path),
    ])
    if r.returncode != 0:
        raise RuntimeError(f'ffprobe failed on {path}: {r.stderr.decode(errors="ignore")[:500]}')
    d = json.loads(r.stdout.decode('utf-8', errors='ignore'))
    if not d.get('streams'):
        raise RuntimeError(f'no video stream in {path}')

    v = d['streams'][0]
    fmt = d.get('format', {})

    # exact rational frame rate: prefer avg_frame_rate (stable), fall back to r_frame_rate
    fps = None
    for key in ('avg_frame_rate', 'r_frame_rate'):
        raw = v.get(key) or '0/0'
        try:
            f = Fraction(raw)
            if f > 0:
                fps = f
                break
        except (ZeroDivisionError, ValueError):
            continue
    if fps is None:
        fps = Fraction(24, 1)

    # frame count: nb_frames is sometimes missing; fall back to duration * fps
    nframes = None
    try:
        if v.get('nb_frames') not in (None, 'N/A', '0'):
            nframes = int(v['nb_frames'])
    except (TypeError, ValueError):
        nframes = None
    duration = None
    try:
        duration = float(fmt.get('duration'))
    except (TypeError, ValueError):
        pass
    if nframes is None and duration:
        nframes = int(round(duration * float(fps)))

    # audio presence -- probed separately because we selected v:0 above
    ra = run_capture([FFPROBE, '-v', 'error', '-select_streams', 'a',
                      '-show_entries', 'stream=index', '-of', 'csv=p=0', str(path)])
    has_audio = bool(ra.stdout.decode('utf-8', errors='ignore').strip())

    return {
        'path': str(path),
        'width': int(v['width']),
        'height': int(v['height']),
        'fps': fps,
        'fps_float': float(fps),
        'fps_arg': f'{fps.numerator}/{fps.denominator}',
        'nb_frames': nframes,
        'duration': duration,
        'has_audio': has_audio,
        'pix_fmt': v.get('pix_fmt'),
        'color_range': v.get('color_range'),
        'color_space': v.get('color_space'),
        'color_transfer': v.get('color_transfer'),
        'color_primaries': v.get('color_primaries'),
        'codec_name': v.get('codec_name'),
    }


# ------------------------------------------------------------------- tiling --

def tile_grid(size: int, tile: int, overlap: int) -> tuple[int, int]:
    """Return (n_tiles_along_axis, padded_size).

    padded_size is chosen so the axis is exactly covered by `n` windows of
    `tile` px advancing by (tile - overlap) -- the precondition for torch.unfold.
    """
    if tile <= overlap:
        raise ValueError('--tile must be larger than --overlap')
    step = tile - overlap
    if size <= tile:
        return 1, tile
    n = math.ceil((size - tile) / step) + 1
    return n, (n - 1) * step + tile


def chunk_budget(tile: int, total_scale: int) -> int:
    """How many tiles to push through the model in one forward.

    Normalised to 8 tiles of 512px input at 2x output (1024px). The cost per
    tile scales with the OUTPUT tile area, so a 4x chain gets a 4x smaller
    batch than a 2x pass at the same --tile. Measured: 8 tiles @1024px peaks
    around 5-7 GB on an RTX 5090.
    """
    ts = tile * total_scale
    return max(1, int(8 * (1024 * 1024) / (ts * ts)))


def _is_compile_failure(e: BaseException) -> bool:
    """True if this looks like a torch.compile / inductor failure.

    Inductor raises a variety of wrapper types whose names are not stable across
    torch versions, so match on the type name, the module, and the message
    rather than importing the exception classes (which differ by version and
    would turn an optional-feature fallback into an ImportError risk).
    """
    names = {type(e).__name__} | {type(e).__module__}
    for cls in type(e).__mro__:
        names.add(cls.__name__)
        names.add(getattr(cls, '__module__', ''))
    if any('Inductor' in n or 'BackendCompiler' in n or 'Dynamo' in n for n in names):
        return True
    if any('torch._inductor' in n or 'torch._dynamo' in n for n in names):
        return True
    msg = str(e).lower()
    return ('inductor' in msg or 'torch.compile' in msg
            or 'backend compiler' in msg or 'dynamo' in msg)


def axis_ramp(tile_len: int, ramp: int, at_start: bool, at_end: bool,
              device: str = 'cuda') -> 'torch.Tensor':
    """1-D blending weights along one axis.

    Interior edges ramp 0->1 (leading) and 1->0 (trailing) so that, across an
    overlap of `ramp` px, the two neighbouring tiles sum to exactly 1.0 at every
    position. Tiles that touch the image border stay flat at 1.0, so the outer
    frame is never attenuated.
    """
    import torch
    w = torch.ones(tile_len, dtype=torch.float32, device=device)
    if not at_start:
        w[:ramp] = torch.linspace(0.0, 1.0, ramp, dtype=torch.float32, device=device)
    if not at_end:
        w[tile_len - ramp:] = torch.linspace(1.0, 0.0, ramp, dtype=torch.float32,
                                             device=device)
    return w


# ---------------------------------------------------------------- inference --

class Upscaler:
    """Holds one or more chained super-resolution models on the GPU."""

    def __init__(self, model_name: str, passes: int, half: bool,
                 channels_last: bool, compile_model: bool, device: str = 'cuda'):
        import torch

        self.torch = torch
        self.device = device
        self.half = half
        self.passes = passes
        arch, ckpt_name, native_scale, kwargs = MODELS[model_name]
        ckpt = COMFY_MODELS / ckpt_name
        if not ckpt.exists():
            raise FileNotFoundError(
                f'model weights not found: {ckpt}\n'
                f'available: {[p.name for p in COMFY_MODELS.glob("*.pth")]}')

        if arch == 'spandrel':
            from spandrel import ModelLoader
            m = ModelLoader().load_from_file(str(ckpt))
            native_scale = m.scale
            if half and not m.supports_half:
                log('model does not support fp16; forcing fp32')
                self.half = half = False
            model = m.model
        else:
            sd = torch.load(str(ckpt), map_location='cpu', weights_only=False)
            for key in ('params_ema', 'params'):
                if key in sd:
                    sd = sd[key]
                    break

            model = self._build(arch, kwargs, native_scale)
            model.load_state_dict(sd, strict=True)
            del sd
        model.eval()
        if channels_last:
            model = model.to(memory_format=torch.channels_last)
        model = model.to(device)
        if half:
            model = model.half()

        # torch.compile is OPTIONAL and its failure must not kill the run.
        # On this box (torch 2.11.0+cu128 / sm_120) inductor raises
        # `LoweringException: TypeError: object() takes no arguments` while
        # generating the kernel -- a PyTorch bug, not something the pipeline can
        # fix. The compile is also LAZY: it happens on the first forward, so a
        # try/except around torch.compile() alone would not catch it. Keep an
        # eager reference and let run() demote on the first real failure.
        self._eager = model
        self._compiled = False
        self.model = model
        if compile_model:
            log('torch.compile() enabled -- first batch will be slow (compiling)')
            try:
                self.model = torch.compile(model, mode='max-autotune')
                self._compiled = True
            except Exception as e:                      # eager-side failure
                log(f'  WARN: torch.compile() unavailable ({type(e).__name__}: {e}); '
                    f'continuing in eager mode')
                self.model = model

        self.native_scale = native_scale
        self.model_name = model_name
        self.tiles_per_chunk = None      # learned adaptively on the first batch
        n_params = sum(p.numel() for p in model.parameters())
        log(f'model {model_name}: {arch} x{native_scale}, {n_params/1e6:.2f}M params, '
            f'{"fp16" if half else "fp32"}, passes={passes}')

    @staticmethod
    def _build(arch: str, kwargs: dict, scale: int):
        if arch == 'rrdbnet':
            from basicsr.archs.rrdbnet_arch import RRDBNet
            return RRDBNet(scale=scale, **kwargs)
        if arch == 'srvgg':
            from basicsr.archs.srvgg_arch import SRVGGNetCompact
            return SRVGGNetCompact(upscale=scale, **kwargs)
        raise ValueError(f'unknown arch {arch}')

    def run(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """x: (N,C,H,W) on device, already in the model dtype. Returns (N,C,H*s,W*s)."""
        torch = self.torch
        with torch.inference_mode():
            if self._compiled:
                try:
                    return self._forward(x)
                except Exception as e:
                    # Compiled kernels can also fail LAZILY on the first real
                    # forward (inductor codegen errors surface here, not at
                    # torch.compile()). An optional speed-up must never cost the
                    # whole render, so demote to eager and carry on.
                    if not _is_compile_failure(e):
                        raise
                    log(f'  WARN: compiled graph failed at runtime '
                        f'({type(e).__name__}); falling back to eager mode for '
                        f'the rest of this run')
                    self.model = self._eager
                    self._compiled = False
            return self._forward(x)

    def _forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
        y = self.model(x)
        for _ in range(self.passes - 1):
            y = self.model(y)
        return y

    def upscale_frame(self, frame_rgb: 'torch.Tensor', tile: int, overlap: int,
                      fbatch: int) -> 'torch.Tensor':
        """Upscale a batch of full frames using seam-free tiled inference.

        frame_rgb: (B,3,H,W) float32 in [0,1] on device.
        Returns (B,3,H*s,W*s) float32 in [0,1] on device.
        """
        import torch
        import torch.nn.functional as F

        B, C, H, W = frame_rgb.shape
        s = self.native_scale ** self.passes
        nr, ph = tile_grid(H, tile, overlap)
        nc, pw = tile_grid(W, tile, overlap)
        step = tile - overlap

        # reflect-pad so the image is exactly covered by the tile windows
        if ph != H or pw != W:
            frame_rgb = F.pad(frame_rgb, (0, pw - W, 0, ph - H), mode='reflect')

        x = frame_rgb.contiguous(memory_format=torch.channels_last)
        if self.half:
            x = x.half()

        Ts = tile * s
        ramp = min(overlap * s, Ts)

        # --- extract all tiles as a view, then flatten to one big batch ---
        tiles = x.unfold(2, tile, step).unfold(3, tile, step)     # (B,C,nr,nc,tile,tile)
        tiles = tiles.permute(0, 2, 3, 1, 4, 5).reshape(B * nr * nc, C, tile, tile)

        # --- one forward for everything, chunked to respect VRAM ---
        # RRDBNet keeps many 64-channel intermediates alive per tile, so the
        # tile batch -- not the output size -- is what drives peak VRAM. The
        # cost per tile scales with the OUTPUT tile area (Ts = tile * total
        # scale), so a 4x chain needs 4x smaller batches than a 2x pass at the
        # same --tile. We normalise against an 8-tile @ 1024px-output budget and
        # back off automatically on OOM, remembering what worked for the run.
        if self.tiles_per_chunk is None:
            self.tiles_per_chunk = chunk_budget(tile, s)
        tpc = max(1, min(self.tiles_per_chunk, tiles.shape[0]))
        out_chunks = []
        i = 0
        while i < tiles.shape[0]:
            chunk = tiles[i:i + tpc]
            try:
                out_chunks.append(self.run(chunk))
            except RuntimeError as e:
                if 'out of memory' not in str(e).lower():
                    raise
                torch.cuda.empty_cache()
                if tpc == 1:
                    raise
                tpc = max(1, tpc // 2)
                log(f'  OOM: reducing tile batch to {tpc} and retrying')
                continue
            self.tiles_per_chunk = tpc
            i += chunk.shape[0]
        outs = torch.cat(out_chunks, dim=0).float().clamp_(0.0, 1.0)
        del tiles, out_chunks

        # --- weighted accumulation with separable ramps ---
        Hp, Wp = ph * s, pw * s
        canvas = torch.zeros(B, C, Hp, Wp, dtype=torch.float32, device=frame_rgb.device)
        wsum = torch.zeros(1, 1, Hp, Wp, dtype=torch.float32, device=frame_rgb.device)

        # cache the 1-D ramps: nr distinct row weights, nc distinct column weights
        dev = frame_rgb.device
        row_w = [axis_ramp(Ts, ramp, r == 0, r == nr - 1, dev) for r in range(nr)]
        col_w = [axis_ramp(Ts, ramp, c == 0, c == nc - 1, dev) for c in range(nc)]

        outs = outs.view(B, nr, nc, C, Ts, Ts)
        for r in range(nr):
            oy = r * step * s
            wy = row_w[r].view(1, 1, Ts, 1)
            for c in range(nc):
                ox = c * step * s
                mask = wy * col_w[c].view(1, 1, 1, Ts)          # (1,1,Ts,Ts)
                blk = outs[:, r, c]                              # (B,C,Ts,Ts)
                canvas[:, :, oy:oy + Ts, ox:ox + Ts] += blk * mask
                wsum[:, :, oy:oy + Ts, ox:ox + Ts] += mask
        del outs

        canvas /= wsum.clamp_min(1e-6)
        del wsum
        # crop the reflect padding back off
        return canvas[:, :, :H * s, :W * s].contiguous()


# ------------------------------------------------------------------ pipeline --

def read_exact(stream, n: int) -> bytes:
    """Read exactly n bytes, or fewer at EOF."""
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return bytes(buf)


def build_encoder_cmd(args, src: dict, up_w: int, up_h: int, out_w: int, out_h: int,
                      audio_mode: str, n_frames_limit: int | None) -> list[str]:
    cmd = [FFMPEG, '-nostdin', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{up_w}x{up_h}', '-r', src['fps_arg'], '-i', '-']

    if audio_mode != 'none':
        cmd += ['-i', src['path']]

    cmd += ['-map', '0:v:0']
    if audio_mode != 'none':
        cmd += ['-map', '1:a:0?']          # '?' -> optional; fixes the silent-input abort

    if out_w != up_w or out_h != up_h:
        cmd += ['-vf', f'scale={out_w}:{out_h}:flags=lanczos']

    codec = args.codec
    if codec == 'x264':
        cmd += ['-c:v', 'libx264', '-crf', str(args.crf), '-preset', args.preset]
    elif codec == 'x265':
        cmd += ['-c:v', 'libx265', '-crf', str(args.crf), '-preset', args.preset,
                '-tag:v', 'hvc1']
    elif codec == 'nvenc_h264':
        cmd += ['-c:v', 'h264_nvenc', '-rc', 'vbr', '-cq', str(args.crf),
                '-preset', 'p5', '-b:v', '0']
    elif codec == 'nvenc_hevc':
        cmd += ['-c:v', 'hevc_nvenc', '-rc', 'vbr', '-cq', str(args.crf),
                '-preset', 'p5', '-b:v', '0', '-tag:v', 'hvc1']
    else:
        raise ValueError(f'unknown codec {codec}')

    cmd += ['-pix_fmt', 'yuv420p', '-movflags', '+faststart']

    # colour tags: carry the source's tags through, default to BT.709 video range
    cs = src.get('color_space') or 'bt709'
    cp = src.get('color_primaries') or 'bt709'
    ct = src.get('color_transfer') or 'bt709'
    cr = src.get('color_range') or 'tv'
    cmd += ['-colorspace', cs, '-color_primaries', cp, '-color_trc', ct, '-color_range', cr]

    if audio_mode == 'copy':
        cmd += ['-c:a', 'copy']
    elif audio_mode == 'encode':
        cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000']

    if n_frames_limit:
        cmd += ['-frames:v', str(n_frames_limit)]

    cmd += [args.output]
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(
        description='Streaming, fps-faithful, adaptive video super-resolution.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output', nargs='?')
    ap.add_argument('--model', choices=sorted(MODELS), default=None,
                    help='default: x2plus when --scale 2, x4v3 when --scale 4')
    ap.add_argument('--scale', type=int, choices=(2, 4), default=2)
    ap.add_argument('--passes', type=int, default=1,
                    help='chain the model this many times (2 with x2plus == v1 2x+2x chain)')
    ap.add_argument('--tile', type=int, default=512)
    ap.add_argument('--overlap', type=int, default=32)
    ap.add_argument('--fbatch', type=int, default=0,
                    help='frames per GPU batch (0 = auto, default)')
    ap.add_argument('--out-width', type=int, default=None, help='final lanczos resize')
    ap.add_argument('--out-height', type=int, default=None)
    ap.add_argument('--codec', default='x264',
                    choices=('x264', 'x265', 'nvenc_h264', 'nvenc_hevc'))
    ap.add_argument('--crf', type=float, default=18)
    ap.add_argument('--preset', default='medium')
    ap.add_argument('--audio', default='auto', choices=('auto', 'copy', 'encode', 'none'))
    ap.add_argument('--half', dest='half', action='store_true', default=True)
    ap.add_argument('--no-half', dest='half', action='store_false')
    ap.add_argument('--channels-last', action='store_true', default=True)
    ap.add_argument('--compile', action='store_true', default=False)
    ap.add_argument('--clear-every', type=int, default=0,
                    help='empty the CUDA cache every N frames (0 = never; v1 did it every frame)')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--frames', type=int, default=None, help='process only N frames (testing)')
    ap.add_argument('--report', default=None, help='write a JSON run report here')
    ap.add_argument('--info', action='store_true', help='probe the input and exit')
    ap.add_argument('--dry-run', action='store_true', help='probe + plan, no GPU work')
    args = ap.parse_args()

    src_path = Path(args.input)
    if not src_path.exists():
        log(f'ERROR: input not found: {src_path}')
        return 2

    log(f'ffmpeg : {FFMPEG}  [{FFMPEG_SOURCE}]')
    log(f'         version {ffmpeg_version(FFMPEG)}')
    src = probe(src_path)
    log(f'input  : {src_path.name}  {src["width"]}x{src["height"]}  '
        f'{src["fps_float"]:.4f}fps ({src["fps_arg"]})  '
        f'{src["nb_frames"]} frames  audio={"yes" if src["has_audio"] else "NO"}  '
        f'colorspace={src["color_space"]} range={src["color_range"]}')

    model_name = args.model or ('x2plus' if args.scale == 2 else 'x4v3')
    _, _, native_scale, _ = MODELS[model_name]
    if native_scale != args.scale:
        log(f'ERROR: --scale {args.scale} conflicts with model {model_name} '
            f'(native x{native_scale}). Use --passes to chain.')
        return 2

    total_scale = native_scale ** args.passes
    up_w = src['width'] * total_scale
    up_h = src['height'] * total_scale
    out_w = args.out_width or up_w
    out_h = args.out_height or up_h

    if out_w % 2 or out_h % 2:
        log(f'WARN: yuv420p needs even dimensions; {out_w}x{out_h} -> '
            f'{out_w - out_w % 2}x{out_h - out_h % 2}')
        out_w -= out_w % 2
        out_h -= out_h % 2

    nr, ph = tile_grid(src['height'], args.tile, args.overlap)
    nc, pw = tile_grid(src['width'], args.tile, args.overlap)
    log(f'plan   : {model_name} x{native_scale} x{args.passes} pass(es) -> {total_scale}x  '
        f'{src["width"]}x{src["height"]} -> {up_w}x{up_h}'
        + (f' -> lanczos {out_w}x{out_h}' if (out_w, out_h) != (up_w, up_h) else ''))
    log(f'tiles  : {nr}x{nc} = {nr * nc} per frame (tile={args.tile} overlap={args.overlap} '
        f'ramp={args.overlap * total_scale}px)')

    if args.info:
        print(json.dumps(src, indent=2, default=str))
        return 0
    if args.dry_run:
        log('dry run -- no GPU work performed')
        return 0
    if not args.output:
        log('ERROR: output path required (unless --info/--dry-run)')
        return 2

    # audio decision
    audio_mode = args.audio
    if audio_mode == 'auto':
        audio_mode = 'copy' if src['has_audio'] else 'none'
    if audio_mode != 'none' and not src['has_audio']:
        log(f'WARN: --audio {audio_mode} requested but input has no audio; disabling')
        audio_mode = 'none'
    if args.frames and audio_mode != 'none':
        log('WARN: --frames limits video only; disabling audio to avoid desync')
        audio_mode = 'none'

    import numpy as np
    import torch

    torch.backends.cudnn.benchmark = True

    upscaler = Upscaler(model_name, args.passes, args.half,
                        args.channels_last, args.compile)

    # frame batching: fill the per-forward tile budget without exceeding it.
    # Measured on a 5090: batching frames beyond the budget is slower AND uses
    # more VRAM (extra canvas/weight buffers), so cap fbatch at what the budget
    # can absorb.
    per_frame_tiles = nr * nc
    budget = chunk_budget(args.tile, total_scale)
    fbatch = args.fbatch
    if fbatch <= 0:
        fbatch = max(1, min(4, budget // max(per_frame_tiles, 1)))
    log(f'batch  : {fbatch} frame(s) x {per_frame_tiles} tiles = '
        f'{fbatch * per_frame_tiles} tiles per forward '
        f'(budget {budget}, model chunked if exceeded)')

    enc_cmd = build_encoder_cmd(args, src, up_w, up_h, out_w, out_h, audio_mode, args.frames)
    log(f'encode : {" ".join(enc_cmd[:6])} ... {enc_cmd[-1]}')

    # ---- decoder ----
    dec_cmd = [FFMPEG, '-nostdin', '-loglevel', 'error', '-i', str(src_path),
               '-map', '0:v:0']
    if args.start:
        dec_cmd += ['-ss', str(args.start / src['fps_float'])]
    dec_cmd += ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    if args.frames:
        dec_cmd += []  # frame limiting handled on the encoder side

    frame_bytes = src['width'] * src['height'] * 3
    log(f'pipe   : rawvideo rgb24 {frame_bytes/1e6:.2f} MB/frame, no disk intermediate')

    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    t_start = time.time()
    n_done = 0
    n_fp32_retry = 0
    t_decode = t_infer = t_encode = 0.0
    pending: list[np.ndarray] = []
    limit = args.frames

    def flush(batch_frames: list) -> int:
        """Upscale a list of uint8 HWC frames, write them out. Returns frames written."""
        nonlocal n_fp32_retry
        t0 = time.time()
        arr = np.stack(batch_frames, axis=0)                       # (B,H,W,3)
        t = torch.from_numpy(arr).to(torch.float32).div_(255.0)
        t = t.permute(0, 3, 1, 2).contiguous().to('cuda', non_blocking=True)
        t_in = time.time()
        y = upscaler.upscale_frame(t, args.tile, args.overlap, fbatch)
        if args.half and not torch.isfinite(y).all():
            n_fp32_retry += len(batch_frames)
            log(f'  WARN: fp16 produced NaN/Inf on frames '
                f'{n_done - len(batch_frames) + 1}..{n_done}; retrying in fp32')
            was_half = upscaler.half
            upscaler.half = False
            upscaler.model.float()
            t32 = t.float()
            y = upscaler.upscale_frame(t32, args.tile, args.overlap, fbatch)
            upscaler.half = was_half
            if was_half:
                upscaler.model.half()
        torch.cuda.synchronize()
        t_out = time.time()
        y8 = (y.clamp_(0, 1) * 255.0).round_().to(torch.uint8)
        y8 = y8.permute(0, 2, 3, 1).contiguous().cpu().numpy()
        for f in y8:
            enc.stdin.write(f.tobytes())
        enc.stdin.flush()
        t_end = time.time()
        del t, y, y8, arr
        return t_in - t0, t_out - t_in, t_end - t_out

    try:
        while True:
            if limit is not None and n_done + len(pending) >= limit:
                break
            buf = read_exact(dec.stdout, frame_bytes)
            if len(buf) < frame_bytes:
                break
            t0 = time.time()
            frame = np.frombuffer(buf, dtype=np.uint8).reshape(
                src['height'], src['width'], 3).copy()
            t_decode += time.time() - t0

            pending.append(frame)
            if len(pending) >= fbatch:
                a, b, c = flush(pending)
                t_infer += b
                t_encode += c
                n_done += len(pending)
                pending = []
                if args.clear_every and n_done % args.clear_every == 0:
                    torch.cuda.empty_cache()
                if n_done % 24 == 0 or n_done == 1:
                    el = time.time() - t_start
                    eta = el / n_done * ((limit or src['nb_frames'] or n_done) - n_done)
                    log(f'  {n_done}/{limit or src["nb_frames"] or "?"} frames  '
                        f'{el:.0f}s elapsed  ETA {max(eta, 0):.0f}s  '
                        f'peak VRAM {torch.cuda.max_memory_allocated()/2**30:.2f} GB')

        if pending:
            a, b, c = flush(pending)
            t_infer += b
            t_encode += c
            n_done += len(pending)
    finally:
        try:
            dec.stdout.close()
        except Exception:
            pass
        dec.wait()
        try:
            enc.stdin.close()
        except Exception:
            pass
        rc = enc.wait()

    elapsed = time.time() - t_start
    peak_vram = torch.cuda.max_memory_allocated() / 2**30

    if rc != 0:
        log(f'ERROR: encoder exited with code {rc}')
        return 1
    if n_done == 0:
        log('ERROR: no frames were decoded')
        return 1

    out_path = Path(args.output)
    log(f'DONE   : {n_done} frames in {elapsed:.1f}s '
        f'({n_done/elapsed:.2f} fps, decode {t_decode:.1f}s / infer {t_infer:.1f}s / '
        f'encode {t_encode:.1f}s)')
    log(f'peak VRAM: {peak_vram:.2f} GB'
        + (f'  | fp32 retries: {n_fp32_retry}' if n_fp32_retry else ''))
    if out_path.exists():
        log(f'output : {out_path}  {out_path.stat().st_size/2**20:.1f} MB')
        rp = run_capture([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=width,height,r_frame_rate,nb_frames',
                          '-show_entries', 'format=duration', '-of', 'default=nw=1',
                          str(out_path)])
        log('verify : ' + ' '.join(rp.stdout.decode(errors='ignore').split()))

    if args.report:
        report = {
            'input': src, 'output': str(out_path),
            'model': model_name, 'passes': args.passes, 'total_scale': total_scale,
            'tile': args.tile, 'overlap': args.overlap, 'fbatch': fbatch,
            'half': args.half, 'channels_last': args.channels_last, 'compile': args.compile,
            'codec': args.codec, 'crf': args.crf, 'audio_mode': audio_mode,
            'frames': n_done, 'elapsed_s': elapsed,
            'fps_throughput': n_done / elapsed,
            't_decode_s': t_decode, 't_infer_s': t_infer, 't_encode_s': t_encode,
            'peak_vram_gb': peak_vram, 'fp32_retries': n_fp32_retry,
            'out_width': out_w, 'out_height': out_h,
            'out_bytes': out_path.stat().st_size if out_path.exists() else None,
        }
        Path(args.report).write_text(json.dumps(report, indent=2, default=str),
                                     encoding='utf-8')
        log(f'report : {args.report}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
