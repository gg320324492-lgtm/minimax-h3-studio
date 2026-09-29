"""2K upscale via FlashVSR v1.1 (ComfyUI), chunked at shot boundaries.

FlashVSR preallocates the whole output batch in CPU RAM (~25 MB/frame fp16),
so a 3440-frame film cannot go through in one shot even in tiny-long mode.
We cut the picture lock at shot boundaries into <=MAXF-frame chunks, upscale
each chunk (mode tiny-long), then concat. Cuts land on hard shot changes, so
no motion seams.

Usage: python upscale_2k.py IN.mp4 OUT.mp4
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, FFPROBE, prepend_to_path  # noqa: E402
prepend_to_path()

SERVER = 'http://127.0.0.1:8188'
PROJECT = Path(r'E:/Minimax-H3/third_lantern')
COMFY_INPUT = Path(r'E:/ComfyUI/input')
COMFY_OUTPUT = Path(r'E:/ComfyUI/output')
TMP = PROJECT / '07_edit' / '2k_chunks'
MAXF = 900


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, data=None, timeout=28800):
    req = urllib.request.Request(
        f'{SERVER}{path}',
        data=json.dumps(data).encode() if data is not None else None,
        method='POST' if data is not None else 'GET',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors='ignore')[-800:])


def shot_frame_chunks(src, maxf=MAXF):
    """Chunk per shot (capped at maxf) - empirically fastest.

    FlashVSR tiny-long cost scales SUPERLINEARLY with chunk length on this
    box: 226f chunk ~= 2.5 min, 900f chunk ~= 15+ min. Keep chunks at shot
    granularity; joins land on hard cuts so no seams.
    """
    tl = json.loads((PROJECT / '00_project' / 'timeline.json').read_text(encoding='utf-8'))
    fps = 24.0
    cuts = [0]
    for b in tl['shot_boundaries'].values():
        cuts.append(round(b['end'] * fps))
    cuts.append(int(tl['total_duration'] * fps))
    cuts = sorted(set(cuts))
    chunks = []
    start = cuts[0]
    for c in cuts[1:]:
        if c - start > maxf:
            while c - start > maxf:
                chunks.append((start, start + maxf))
                start += maxf
        chunks.append((start, c))
        start = c
    return chunks


def upscale_chunk(chunk_path, out_path, idx):
    in_name = f'lz3_2k_chunk_{idx}.mp4'
    shutil.copy2(chunk_path, COMFY_INPUT / in_name)

    def n(cls, **inp):
        return {'class_type': cls, 'inputs': inp}

    graph = {
        '10': n('LoadVideo', file=in_name),
        '11': n('GetVideoComponents', video=['10', 0]),
        '12': n('FlashVSRInitPipe',
                model='FlashVSR-v1.1', mode='tiny-long', alt_vae='none',
                force_offload=True, precision='bf16', device='auto',
                attention_mode='sparse_sage_attention'),
        '13': n('FlashVSRNodeAdv',
                pipe=['12', 0], frames=['11', 0], scale=2,
                color_fix=True, tiled_vae=True, tiled_dit=True,
                tile_size=512, tile_overlap=32, unload_dit=False,
                sparse_ratio=2.0, kv_ratio=3.0, local_range=11,
                seed=410924 + idx),
        '14': n('CreateVideo', images=['13', 0], fps=24, bit_depth=8),
        '15': n('SaveVideo', video=['14', 0], filename_prefix=f'lz3_2k_out_{idx}',
                format='auto'),
    }
    resp = api('/prompt', {'prompt': graph})
    if 'prompt_id' not in resp:
        raise RuntimeError(f'submit error: {json.dumps(resp)[:1200]}')
    pid = resp['prompt_id']
    log(f'chunk {idx}: submitted {pid}')
    t0 = time.time()
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                raise RuntimeError(f'FAILED: {str(st.get("messages"))[-600:]}')
            if st.get('completed') or 'outputs' in rec:
                break
        time.sleep(8)
    found = []
    for node_out in (rec.get('outputs') or {}).values():
        for key in ('images', 'videos', 'gifs'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(COMFY_OUTPUT / sub / item['filename'])
    srcf = next((c for c in found if c.exists()), None)
    if srcf is None:
        raise RuntimeError(f'chunk {idx}: no output')

    # FlashVSR pads to 8n+5 internally and its output frame count can differ
    # from the input - which would drift the concat timeline (101 frames were
    # lost over 18 chunks once). Force the output to exactly the input count.
    n_in = int(subprocess.check_output(
        [FFPROBE, '-v', 'error', '-select_streams', 'v:0',
         '-count_frames', '-show_entries', 'stream=nb_read_frames',
         '-of', 'csv=p=0', str(chunk_path)]).decode().strip())
    n_out = int(subprocess.check_output(
        [FFPROBE, '-v', 'error', '-select_streams', 'v:0',
         '-count_frames', '-show_entries', 'stream=nb_read_frames',
         '-of', 'csv=p=0', str(srcf)]).decode().strip())
    if n_out != n_in:
        log(f'chunk {idx}: frame count mismatch in={n_in} out={n_out} -> fixing')
        fixed = out_path.parent / f'chunk_fix_{idx:02d}.mp4'
        if n_out < n_in:
            vf = (f'tpad=stop_mode=clone:stop_duration={((n_in - n_out) / 24.0):.6f},'
                  f'trim=end_frame={n_in},setpts=PTS-STARTPTS')
        else:
            vf = f'trim=end_frame={n_in},setpts=PTS-STARTPTS'
        run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(srcf),
             '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '14',
             '-bf', '0', '-an', str(fixed)])
        shutil.copy2(fixed, out_path)
    else:
        shutil.copy2(srcf, out_path)
    log(f'chunk {idx}: done in {(time.time()-t0)/60:.1f} min ({n_in}/{n_out} frames) -> {out_path.name}')


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    TMP.mkdir(parents=True, exist_ok=True)

    chunks = shot_frame_chunks(src)
    log(f'{len(chunks)} chunks, frames: {chunks}')

    outs = []
    for i, (f0, f1) in enumerate(chunks):
        out_path = TMP / f'chunk_{i:02d}.mp4'
        if out_path.exists() and out_path.stat().st_size > 100_000:
            log(f'chunk {i}: skip (exists)')
            outs.append(out_path)
            continue
        chunk_in = TMP / f'chunk_in_{i:02d}.mp4'
        run([FFMPEG, '-y', '-loglevel', 'error',
             '-ss', f'{f0 / 24.0:.6f}', '-i', str(src),
             '-t', f'{(f1 - f0) / 24.0:.6f}',
             '-vf', 'setsar=1,fps=24',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-bf', '0', '-an',
             str(chunk_in)])
        upscale_chunk(chunk_in, out_path, i)
        outs.append(out_path)

    listing = TMP / 'concat.txt'
    listing.write_text(''.join(f"file '{o.as_posix()}'\n" for o in outs), encoding='utf-8')
    run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
         '-i', str(listing), '-c', 'copy', str(dst)])
    log(f'ALL DONE -> {dst} ({dst.stat().st_size/1e6:.0f}MB)')


if __name__ == '__main__':
    main()
