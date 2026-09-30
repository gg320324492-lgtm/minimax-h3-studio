"""FixAll v3: Regenerate ALL shots to spec durations (~60s total).

Frame grid: 17k+5. Validated lengths and durations @24fps:
  22=0.92s  56=2.33s  124=5.17s  141=5.88s  192=8.00s  226=9.42s

Key changes vs previous version:
- All shots regenerated at spec lengths (plan: sharded-scribbling-nygaard)
- S03C uses the v2 crash prompt that produced visible debris
- S06 gets 2 takes (dialogue shot, pick best)
- Seeds recorded into 00_project/seed_manifest.json AT GENERATION TIME
"""


# --- ffmpeg binary resolution -------------------------------------------------
# PATH `ffmpeg` on this machine is GNU Octave's bundled 4.2.11, not a normal
# install, so every encode silently depended on a third-party app. Resolve via
# ffmpeg_env (repo-bundled 7.1.1 by default; MINIMAX_FFMPEG_LEGACY=1 to pin the
# legacy PATH binary for byte-comparable re-runs).
import sys as _sys, os as _os  # noqa: E402
if r'E:\Minimax-H3' not in _sys.path:
    _sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()
# -----------------------------------------------------------------------------
import json
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# P0.3: 共享的有界轮询（替代本文件内的 while True 副本）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comfy_utils import wait_for_prompt  # noqa: E402

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')
PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
SEED_MANIFEST = PROJECT / '00_project' / 'seed_manifest.json'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, method='GET', data=None):
    url = f'{SERVER}{path}'
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8'))


def record_seed(shot_id, take, seed, length_frames):
    """Record actual generation seed immediately (fix #6)."""
    manifest = {}
    if SEED_MANIFEST.exists():
        try:
            manifest = json.loads(SEED_MANIFEST.read_text(encoding='utf-8'))
        except Exception:
            manifest = {}
    manifest.setdefault('project', 'ceo_mindread_ep01')
    manifest.setdefault('created_at', time.strftime('%Y-%m-%d %H:%M:%S'))
    manifest.setdefault('model', 'minimax_h3_ref2va_pruned_int8_convrot.safetensors')
    manifest.setdefault('pipeline', 'R2V + turbo 4step LoRA, cfg=1, res_multistep/simple')
    shots = manifest.setdefault('shots', {})
    entry = shots.setdefault(shot_id, {})
    entry[f'seed_T{take:02d}'] = seed
    entry['length_frames'] = length_frames
    SEED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SEED_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')


def workflow_to_prompt(workflow, custom_prompt, ref_images, custom_seed, custom_length, width, height):
    nodes = workflow.get('nodes', [])
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    prompt = {}
    for n in nodes:
        if n.get('type') in SKIP:
            continue
        nid = str(n['id'])
        inputs = {}
        named = n.get('widgets_values_named') or {}
        inputs.update(named)
        names = n.get('widgets_names') or []
        values = n.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]
        if nid == '138':
            inputs['value'] = custom_prompt
        if nid in ('137', '139') and ref_images:
            slot = '0' if nid == '137' else '1'
            if slot in ref_images:
                inputs['image'] = ref_images[slot]
        if nid == '136':
            inputs['length'] = custom_length
            inputs['noise_seed'] = custom_seed
            inputs['prompt'] = custom_prompt
            inputs['width'] = width
            inputs['height'] = height
        if nid == '132':
            inputs['value'] = custom_length / 24.0
        for inp in (n.get('inputs') or []):
            lid = inp.get('link'); name = inp.get('name')
            if lid is None or name is None:
                continue
            if name in inputs:
                continue
            if lid in link_map:
                src_id, src_slot = link_map[lid]
                inputs[name] = [str(src_id), src_slot]
        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt


def find_latest_video():
    out_dir = Path(r'E:\ComfyUI\output')
    files = list(out_dir.glob('MiniMax_H3*.mp4'))
    if not files:
        files = list(out_dir.rglob('*.mp4'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def outputs_from_history(rec):
    """Absolute paths of every file this specific prompt saved.

    Replaces mtime-guessing: /history/<pid> carries the exact filename the
    SaveVideo node wrote, so a concurrent job can never be mistaken for ours.
    """
    out_dir = Path(r'E:\ComfyUI\output')
    found = []
    for node_out in (rec.get('outputs') or {}).values():
        if not isinstance(node_out, dict):
            continue
        for key in ('images', 'videos', 'gifs', 'audio'):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get('filename'):
                    sub = item.get('subfolder') or ''
                    found.append(out_dir / sub / item['filename'])
    return found


def read_recorded_seed(shot_id, take):
    """Seed already on record for this take, or None."""
    if not SEED_MANIFEST.exists():
        return None
    try:
        manifest = json.loads(SEED_MANIFEST.read_text(encoding='utf-8'))
    except Exception:
        return None
    return (manifest.get('shots', {}).get(shot_id, {}) or {}).get(f'seed_T{take:02d}')


def gen_shot(slug, shot_id, take, shot_dir, prompt_text, ref_images, custom_seed, length_frames,
             width=768, height=1344):
    log(f'  GEN: {slug} (length={length_frames}, seed={custom_seed})')
    shot_dir.mkdir(parents=True, exist_ok=True)
    dst = shot_dir / f'{slug}.mp4'
    if dst.exists() and dst.stat().st_size > 100000:
        prev = read_recorded_seed(shot_id, take)
        if prev is None:
            log(f'    SKIP: {dst.name} exists ({dst.stat().st_size/1024:.0f}KB); '
                f'recording seed {custom_seed}')
            record_seed(shot_id, take, custom_seed, length_frames)
        elif prev != custom_seed:
            # the file on disk was produced with a different seed -- do NOT
            # overwrite the manifest, or the recorded seed stops matching the take
            log(f'    SKIP: {dst.name} exists; keeping recorded seed {prev} '
                f'(requested {custom_seed} would not match the file on disk)')
        else:
            log(f'    SKIP: {dst.name} exists ({dst.stat().st_size/1024:.0f}KB)')
        return dst
    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    api_prompt = workflow_to_prompt(
        wf, prompt_text, ref_images,
        custom_seed=custom_seed,
        custom_length=length_frames,
        width=width, height=height
    )
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    if 'error' in resp:
        log(f'  ERROR: {resp["error"]["type"]}: {resp["error"]["message"]}')
        return None
    pid = resp.get('prompt_id')
    log(f'    pid={pid}')
    rec = None
    # P0.3: bounded polling (was an unbounded while-True loop; R3)
    rec = wait_for_prompt(api, pid, deadline_s=DEADLINE_S, log=log)
    if rec is None:
        return None
    time.sleep(2)
    # Prefer the exact file this prompt recorded; only fall back to newest-mtime
    # if the history carries no output entry.
    candidates = outputs_from_history(rec or {})
    src = next((c for c in candidates if c.exists()), None)
    if src is None:
        log('    WARN: no output recorded in history; falling back to newest-mtime')
        src = find_latest_video()
    if not src:
        log('    No output found!')
        return None
    shutil.copy2(str(src), str(dst))
    log(f'    saved: {dst}')
    record_seed(shot_id, take, custom_seed, length_frames)
    return dst


# ---- Prompts (S03C uses the v2 crash prompt that visibly shows debris) ----

# ---- Generation config (P0 audit: extracted from this file) ----
# Prompts/seeds are project IP and live in a gitignored JSON; this file stays
# tracked so the P0.3 bounded-polling fix cannot drift off-machine.
import json as _json
_GEN = _json.loads((PROJECT / "00_project" / "h3_generation.json").read_text(encoding="utf-8"))
REFS = _GEN["refs"]
for _k, _v in _GEN["prompts"].items():
    globals()[_k] = _v
SHOTS = {}
for _sid, _s in _GEN["shots"].items():
    _pk = _s.pop("prompt_key", None)
    SHOTS[_sid] = dict(_s, prompt=globals()[_pk] if _pk else "")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ['all']
    if targets == ['all']:
        targets = list(SHOTS.keys())

    total_gens = sum(SHOTS[s]['takes'] for s in targets if s in SHOTS)
    log(f'FixAll v3 regeneration. Shots: {targets} ({total_gens} takes)')

    t_start = time.time()
    for shot_id in targets:
        cfg = SHOTS.get(shot_id)
        if not cfg:
            log(f'Unknown shot: {shot_id}')
            continue
        log(f'\n========== {shot_id} ({cfg["length"]} frames) ==========')
        shot_dir = PROJECT / f'03_video_raw/{shot_id}'
        for take in range(1, cfg['takes'] + 1):
            slug = f'{shot_id}_T{take:02d}'
            gen_shot(
                slug=slug, shot_id=shot_id, take=take,
                shot_dir=shot_dir,
                prompt_text=cfg['prompt'],
                ref_images=REFS,
                custom_seed=cfg['seed_base'] + take * 1000,
                length_frames=cfg['length'],
            )

    log(f'\n=== ALL DONE in {(time.time()-t_start)/60:.1f} min ===')


if __name__ == '__main__':
    main()

DEADLINE_S = 3600  # P0.3: ComfyUI job wall-clock budget
