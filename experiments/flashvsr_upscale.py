#!/usr/bin/env python
"""Drive FlashVSR (CVPR 2026, one-step streaming diffusion VSR) through ComfyUI.

Why this exists
---------------
The local Real-ESRGAN path is a per-frame, tile-averaging CNN. It has two
ceilings the project has already measured:
  * chained 2x+2x loses ~65% of Laplacian sharpness (OPTIMAL_PIPELINE_REPORT.md)
  * it is temporally blind, so nothing stops tile or frame-level flicker

FlashVSR is a one-step diffusion streaming VSR model: it is temporally aware by
construction, runs ~17 FPS at 768x1408 on an A100, and its own tiled DiT uses
feather-masked blending. On this box it is the single biggest quality upgrade
available for the 768x1344 -> 1080x1920 delivery path.

This driver talks to a running ComfyUI over its HTTP API (same pattern as
gen_keyframes_v3.py) and discovers the node's input schema at runtime via
/object_info, so it keeps working if the custom node adds or renames inputs.

Prerequisites (see tools/flashvsr_setup.py):
  * ComfyUI custom node  lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast
  * models in ComfyUI/models/FlashVSR-v1.1/  (~7 GB)
  * ComfyUI running on --listen (default http://127.0.0.1:8188)

Usage:
  python flashvsr_upscale.py in.mp4 out.mp4 --scale 2
  python flashvsr_upscale.py in.mp4 out.mp4 --mode tiny-long --scale 4 --tiled-dit
  python flashvsr_upscale.py --check                 # is everything in place?
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

COMFY = Path(r'E:\ComfyUI')
INPUT_DIR = COMFY / 'input'
OUTPUT_DIR = COMFY / 'output'
NODE_DIR = COMFY / 'custom_nodes' / 'ComfyUI-FlashVSR_Ultra_Fast'


def log(msg: str) -> None:
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


# ------------------------------------------------------------------- comfy api --

def api(server: str, path: str, method: str = 'GET', data=None, timeout: int = 3600):
    url = f'{server}{path}'
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw) if raw else {}


def node_schema(server: str, cls: str) -> dict:
    info = api(server, f'/object_info/{cls}')
    if cls not in info:
        raise RuntimeError(
            f'node "{cls}" is not registered. Is the FlashVSR custom node installed '
            f'and did ComfyUI restart? (expected in {NODE_DIR})')
    return info[cls]


def defaults_for(server: str, cls: str) -> dict:
    """Pull every input's default straight from the live node schema."""
    schema = node_schema(server, cls)
    spec = schema.get('input', {})
    out: dict = {}
    for group in ('required', 'optional'):
        for name, meta in (spec.get(group) or {}).items():
            if not isinstance(meta, list) or not meta:
                continue
            t = meta[0]
            opts = meta[1] if len(meta) > 1 and isinstance(meta[1], dict) else {}
            if t == 'COMFY_DYNAMICCOMBO_V3':
                # Cascading combo: the value is one of options[i]['key'], and
                # picking one exposes further nested inputs (e.g. format ->
                # codec). Take the first option as the default; callers that
                # care about the container override it explicitly.
                opts = (meta[1] or {}).get('options') or []
                out[name] = opts[0].get('key') if opts else None
            elif isinstance(t, list):                    # plain combo
                out[name] = opts.get('default', t[0] if t else None)
            elif t == 'INT':
                out[name] = opts.get('default', 0)
            elif t == 'FLOAT':
                out[name] = opts.get('default', 0.0)
            elif t == 'BOOLEAN':
                out[name] = opts.get('default', False)
            elif t == 'STRING':
                out[name] = opts.get('default', '')
            else:                                        # link-only input
                out[name] = None
    return out


# -------------------------------------------------------------------- workflow --

def build_workflow(server: str, video_name: str, args, out_prefix: str) -> dict:
    """Assemble the FlashVSR graph.

    LoadVideo -> GetVideoComponents -> [FlashVSRInitPipe, FlashVSRNodeAdv]
              -> CreateVideo -> SaveVideo
    """
    pipe = defaults_for(server, 'FlashVSRInitPipe')
    adv = defaults_for(server, 'FlashVSRNodeAdv')

    pipe.update({
        'model': args.model,
        'mode': args.mode,
        'force_offload': not args.keep_loaded,
        'precision': args.precision,
        'attention_mode': args.attention,
    })
    if args.device:
        pipe['device'] = args.device

    adv.update({
        'scale': args.scale,
        'color_fix': not args.no_color_fix,
        'tiled_vae': args.tiled_vae,
        'tiled_dit': args.tiled_dit,
        'tile_size': args.tile_size,
        'tile_overlap': args.tile_overlap,
        'unload_dit': args.unload_dit,
        'seed': args.seed,
    })

    # SaveVideo takes (video, filename_prefix, format, codec) in this ComfyUI
    # build. Hardcoding only the first two failed at execution time with
    # "SaveVideo.execute() missing 1 required positional argument: 'format'" --
    # and because SaveVideo is the LAST node, that threw away a full 155s of
    # completed FlashVSR inference and VAE decoding. Start from the live schema
    # so every input the node declares is present, then override what we set.
    save = defaults_for(server, 'SaveVideo')
    save.update({'video': ['5', 0], 'filename_prefix': out_prefix,
                 # pin a predictable container/codec; "auto" would let the
                 # source stream decide and could yield WebM/AV1 instead of the
                 # MP4/H.264 this project delivers.
                 'format': 'mp4', 'codec': 'h264'})

    return {
        '1': {'class_type': 'LoadVideo', 'inputs': {'file': video_name}},
        '2': {'class_type': 'GetVideoComponents', 'inputs': {'video': ['1', 0]}},
        '3': {'class_type': 'FlashVSRInitPipe', 'inputs': pipe},
        '4': {'class_type': 'FlashVSRNodeAdv', 'inputs': {
            **adv, 'pipe': ['3', 0], 'frames': ['2', 0]}},
        # keep the source audio and the source frame rate
        '5': {'class_type': 'CreateVideo', 'inputs': {
            'images': ['4', 0], 'fps': ['2', 2], 'audio': ['2', 1]}},
        '6': {'class_type': 'SaveVideo', 'inputs': save},
    }


def preflight(server: str) -> bool:
    """Report what is and is not ready. Returns True if a run is possible."""
    ok = True
    try:
        api(server, '/system_stats', timeout=10)
        log(f'ComfyUI reachable at {server}')
    except Exception as e:                                   # noqa: BLE001
        log(f'FAIL  ComfyUI not reachable at {server} ({type(e).__name__})')
        log('      start it with: cd /e/ComfyUI && venv/Scripts/python.exe main.py '
            '--listen 0.0.0.0 --port 8188')
        return False

    if not NODE_DIR.exists():
        log(f'FAIL  custom node missing: {NODE_DIR}')
        log('      run: python tools/flashvsr_setup.py --apply')
        ok = False
    else:
        log(f'ok    custom node present: {NODE_DIR.name}')

    for cls in ('FlashVSRInitPipe', 'FlashVSRNodeAdv'):
        try:
            node_schema(server, cls)
            log(f'ok    node registered: {cls}')
        except Exception as e:                               # noqa: BLE001
            log(f'FAIL  {e}')
            ok = False

    for model in ('FlashVSR', 'FlashVSR-v1.1'):
        d = COMFY / 'models' / model
        if d.exists():
            files = {p.name: p.stat().st_size for p in d.glob('*') if p.is_file()}
            need = {'diffusion_pytorch_model_streaming_dmd.safetensors',
                    'Wan2.1_VAE.pth', 'LQ_proj_in.ckpt', 'TCDecoder.ckpt'}
            missing = need - set(files)
            total = sum(files.values()) / 2 ** 30
            if missing:
                log(f'FAIL  {model}: missing {sorted(missing)}')
                ok = False
            else:
                log(f'ok    {model}: {total:.2f} GB, all 4 files present')
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(
        description='FlashVSR video super-resolution via the ComfyUI API.')
    ap.add_argument('input', nargs='?')
    ap.add_argument('output', nargs='?')
    ap.add_argument('--server', default='http://127.0.0.1:8188')
    ap.add_argument('--check', action='store_true', help='preflight only')
    ap.add_argument('--model', default='FlashVSR-v1.1',
                    choices=('FlashVSR', 'FlashVSR-v1.1'))
    ap.add_argument('--mode', default='tiny', choices=('tiny', 'tiny-long', 'full'),
                    help='tiny=faster, tiny-long=low VRAM for long clips, full=highest quality')
    ap.add_argument('--scale', type=int, default=2, choices=(2, 3, 4),
                    help='upstream recommends 4 unless VRAM-limited')
    ap.add_argument('--precision', default='bf16', choices=('fp16', 'bf16'))
    ap.add_argument('--attention', default='sparse_sage_attention',
                    choices=('sparse_sage_attention', 'block_sparse_attention'),
                    help='sparse_sage supports sm_75..sm_120 (incl. RTX 50 series); '
                         'block_sparse only sm_80..sm_100')
    ap.add_argument('--device', default=None, help='leave unset to use the node default')
    ap.add_argument('--tiled-dit', dest='tiled_dit', action='store_true', default=True)
    ap.add_argument('--no-tiled-dit', dest='tiled_dit', action='store_false')
    ap.add_argument('--tiled-vae', dest='tiled_vae', action='store_true', default=True)
    ap.add_argument('--no-tiled-vae', dest='tiled_vae', action='store_false')
    ap.add_argument('--tile-size', type=int, default=256)
    ap.add_argument('--tile-overlap', type=int, default=24)
    ap.add_argument('--unload-dit', action='store_true', default=False,
                    help='unload the DiT before decoding: lower peak VRAM, slower')
    ap.add_argument('--keep-loaded', action='store_true', default=False,
                    help='do not force-offload weights after the run')
    ap.add_argument('--no-color-fix', action='store_true', default=False)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--timeout', type=int, default=7200)
    ap.add_argument('--report', default=None)
    ap.add_argument('--keep-input', action='store_true',
                    help='leave the copied source in ComfyUI/input')
    args = ap.parse_args()

    if args.check or not args.input:
        return 0 if preflight(args.server) else 1

    src = Path(args.input)
    if not src.exists():
        log(f'ERROR: input not found: {src}')
        return 2
    if not args.output:
        log('ERROR: output path required')
        return 2
    if not preflight(args.server):
        log('preflight failed -- not starting a run')
        return 1

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    video_name = f'flashvsr_src_{int(time.time())}{src.suffix.lower()}'
    staged = INPUT_DIR / video_name
    shutil.copy2(src, staged)
    log(f'staged source -> {staged}')

    out_prefix = f'FlashVSR/{Path(args.output).stem}'
    workflow = build_workflow(args.server, video_name, args, out_prefix)

    t0 = time.time()
    try:
        resp = api(args.server, '/prompt', method='POST',
                   data={'prompt': workflow}, timeout=120)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        log(f'ERROR: ComfyUI rejected the workflow (HTTP {e.code})')
        log(body[:1500])
        return 1

    if 'error' in resp:
        err = resp['error']
        log(f'ERROR: {err.get("type")}: {err.get("message")}')
        for k, v in (err.get('details') or {}).items():
            log(f'  {k}: {str(v)[:300]}')
        return 1

    pid = resp['prompt_id']
    log(f'queued prompt_id={pid}')

    rec = None
    while True:
        try:
            h = api(args.server, f'/history/{pid}', timeout=60)
        except Exception:                                     # noqa: BLE001
            time.sleep(5)
            continue
        if pid in h:
            rec = h[pid]
            status = (rec.get('status') or {})
            if status.get('completed') or rec.get('outputs'):
                log(f'DONE in {time.time() - t0:.1f}s')
                break
            if status.get('status_str') in ('error', 'failed'):
                log(f'FAILED after {time.time() - t0:.1f}s')
                for m in status.get('messages', []):
                    if m and 'error' in str(m[0]).lower():
                        log(f'  {str(m[1])[:400]}')
                return 1
        if time.time() - t0 > args.timeout:
            log(f'TIMEOUT after {args.timeout}s')
            return 1
        time.sleep(5)

    # locate the exact file this prompt wrote
    produced = []
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    produced.append(OUTPUT_DIR / (item.get('subfolder') or '') / item['filename'])
    produced = [p for p in produced if p.exists()]
    if not produced:
        log('ERROR: no output file recorded in the history')
        return 1

    final = Path(args.output)
    final.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(max(produced, key=lambda p: p.stat().st_size), final)
    log(f'output: {final}  {final.stat().st_size / 2**20:.1f} MB')

    if not args.keep_input:
        # `unlink` is best-effort: on a sandboxed/guarded filesystem it can be
        # intercepted (here it raises SAFE_DELETE_BULK_CONFIRM_REQUIRED once a
        # turn's delete budget is spent) and the staged copy would then sit in
        # ComfyUI/input forever, silently. Say so instead of pretending.
        try:
            staged.unlink(missing_ok=True)
        except OSError as e:
            log(f'WARN: could not remove staged input {staged.name} ({e})')
        if staged.exists():
            log(f'WARN: staged input left behind: {staged}')
            log('      remove it by hand, or pass --keep-input to silence this')

    if args.report:
        Path(args.report).write_text(json.dumps({
            'input': str(src), 'output': str(final),
            'model': args.model, 'mode': args.mode, 'scale': args.scale,
            'precision': args.precision, 'attention': args.attention,
            'tiled_dit': args.tiled_dit, 'tile_size': args.tile_size,
            'tile_overlap': args.tile_overlap, 'seed': args.seed,
            'elapsed_s': round(time.time() - t0, 2),
            'out_bytes': final.stat().st_size,
        }, indent=2), encoding='utf-8')
        log(f'report: {args.report}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
