"""Generate OFFICE_MASTER_REFERENCE image.

The office must be locked - same desk position, window direction, pendant light,
executive chair, glass partition, city background.

Uses MiniMax-H3 R2V with existing test image as visual style anchor.
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

sys.path.insert(0, str(Path(__file__).parent))
from comfy_utils import resolve_output_file, wait_for_prompt  # noqa: E402

DEADLINE_S = 3600  # P0.3: ComfyUI job wall-clock budget

SERVER = 'http://127.0.0.1:8188'
WORKFLOW = Path(r'E:\ComfyUI\user\default\workflows\video_minimax_h3_r2v.json')


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


def workflow_to_prompt(workflow, custom_prompt, ref_images, custom_seed, custom_length,
                        width, height):
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
    """Deprecated -- newest-mtime guessing returns the wrong clip whenever any
    other job writes to ComfyUI/output. Use comfy_utils.resolve_output_file(rec).
    """
    raise RuntimeError(
        'find_latest_video() is unsafe (mtime guessing). '
        'Use comfy_utils.resolve_output_file(rec) with the /history record.')


def extract_first_frame(video_path, output_png):
    import subprocess
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(video_path),
        '-frames:v', '1',
        str(output_png)
    ], check=True)
    return output_png


def gen_one(slug, prompt_text, ref_images, output_dir, custom_seed, length_frames):
    log(f'=== GEN: {slug} ===')
    log(f'  prompt: {prompt_text[:200]}')
    log(f'  length: {length_frames} frames')

    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    api_prompt = workflow_to_prompt(
        wf, prompt_text, ref_images,
        custom_seed=custom_seed,
        custom_length=length_frames,
        width=768, height=1344
    )
    log('Submitting...')
    t0 = time.time()
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    if 'error' in resp:
        log(f'ERROR: {resp["error"]["type"]}: {resp["error"]["message"]}')
        return None
    pid = resp.get('prompt_id')
    log(f'pid={pid}')

    # P0.3: bounded polling (was an unbounded while-True loop; R3)
    rec = wait_for_prompt(api, pid, deadline_s=DEADLINE_S, log=log)
    if rec is None:
        return None

    src = resolve_output_file(rec or {})
    if not src:
        log('No output found!')
        return None
    video_dst = output_dir / f'{slug}.mp4'
    shutil.copy2(str(src), str(video_dst))
    log(f'  video: {video_dst}')
    frame_dst = output_dir / f'{slug}_FRAME.png'
    extract_first_frame(video_dst, frame_dst)
    log(f'  frame: {frame_dst}')
    return frame_dst


def main():
    out_dir = Path(r'E:\Minimax-H3\ceo_mindread_ep01\01_reference\office')
    out_dir.mkdir(parents=True, exist_ok=True)

    # OFFICE_WIDE - showing the full office layout
    office_prompt_wide = """Use <Picture 1> as a visual style anchor.

Empty modern premium executive office, vertical 9:16 composition.

Layout (from front to back, camera facing north):
- In the FOREGROUND, lower portion of frame: large modern circular glass and metal pendant light hanging from ceiling, visible at top of frame
- MIDDLE: dark wood executive desk in center, polished surface
- A black leather executive chair behind the desk
- LEFT side: floor-to-ceiling windows showing realistic daytime city skyline
- RIGHT side: minimalist glass partition wall
- BACKGROUND: subtle city skyline through the windows

Material palette: dark wood, neutral gray walls, black leather, glass, brushed metal pendant light.

No people in the scene. Empty office, waiting.

Cinematic, photorealistic, professional corporate photography,
natural daylight coming from windows, soft shadows,
premium Chinese executive office aesthetic,
realistic architectural details, 9:16 vertical composition."""

    log('\n>>> Generating OFFICE_WIDE reference')
    office_wide = gen_one(
        'OFFICE_01_WIDE',
        office_prompt_wide,
        ref_images={'0': 'example.png'},  # Visual style anchor
        output_dir=out_dir,
        custom_seed=33333,
        length_frames=21,
    )

    # OFFICE_DESK - showing the desk from CEO perspective (closer view)
    office_prompt_desk = """Use <Picture 1> as a visual style anchor.

Empty modern premium executive office, vertical 9:16 composition.

Camera POV: looking at the desk from CEO's seated perspective (the chair is in front of camera).

Foreground: dark wood executive desk surface, polished, with some items:
- A leather portfolio folder
- A pen holder with a few pens
- A small ceramic coffee cup

Behind the desk: large floor-to-ceiling windows showing realistic daytime city skyline (tall buildings visible).

ABOVE the desk area: large modern circular glass and metal pendant light, partially visible at top of frame, casting warm light downward.

Background: glass partition wall visible to the side, minimalist modern office interior.

No people in the scene. Empty office.

Cinematic, photorealistic, professional corporate photography,
warm natural daylight from windows, soft shadows,
premium Chinese executive office aesthetic,
realistic architectural details, 9:16 vertical composition."""

    log('\n>>> Generating OFFICE_DESK reference')
    office_desk = gen_one(
        'OFFICE_02_DESK',
        office_prompt_desk,
        ref_images={'0': 'example.png'},
        output_dir=out_dir,
        custom_seed=44444,
        length_frames=21,
    )

    log('\n=== Office Reference Generation Complete ===')
    if office_wide:
        log(f'OFFICE_WIDE: {office_wide}')
    if office_desk:
        log(f'OFFICE_DESK: {office_desk}')


if __name__ == '__main__':
    main()