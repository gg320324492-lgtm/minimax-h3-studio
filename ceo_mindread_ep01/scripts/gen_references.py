"""
Generate MASTER_REFERENCE images using MiniMax-H3 R2V pipeline.

Strategy:
- MiniMax-H3 doesn't have a separate "image generation" mode
- We use the R2V workflow: take a generic reference photo as Picture 1
- The R2V model will generate a 5-second clip that matches the reference
- We extract the first frame as our MASTER_REFERENCE

This ensures consistency: the MASTER_REFERENCE comes from MiniMax-H3 itself,
so subsequent generations using this as reference will look identical.
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
    """Convert UI workflow JSON to API prompt format with injected values.

    Nodes of interest:
    - 138: PrimitiveStringMultiline (prompt)
    - 137, 139: LoadImage (ref images)
    - 136: MiniMaxH3ReferenceToVideo (length, noise_seed)
    - 132: PrimitiveFloat (duration seconds)
    """
    nodes = workflow.get('nodes', [])
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    prompt = {}

    PROMPT_NODE_ID = '138'
    SEED_NODE_ID = '136'
    R2V_NODE_ID = '136'

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
        # Inject prompt
        if nid == PROMPT_NODE_ID:
            inputs['value'] = custom_prompt
        # Inject ref image filenames
        if nid in ('137', '139') and ref_images:
            slot = '0' if nid == '137' else '1'
            if slot in ref_images:
                inputs['image'] = ref_images[slot]
        # Inject R2V parameters
        if nid == R2V_NODE_ID:
            inputs['length'] = custom_length
            inputs['noise_seed'] = custom_seed
            inputs['prompt'] = custom_prompt
            inputs['width'] = width
            inputs['height'] = height
        # Inject duration
        if nid == '132':
            inputs['value'] = custom_length / 24.0  # seconds

        # Handle input links (skip if we already injected)
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
    """Extract first frame from video."""
    import subprocess
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(video_path),
        '-frames:v', '1',
        str(output_png)
    ], check=True)
    return output_png


def gen_reference(slug, prompt_text, ref_images, output_dir, custom_seed=12345, length_frames=21):
    """Generate a 1-second reference video clip and extract first frame."""
    log(f'=== GEN: {slug} ===')
    log(f'  prompt: {prompt_text[:120]}...')
    log(f'  length: {length_frames} frames = {length_frames/24:.1f}s')
    log(f'  ref_images: {ref_images}')

    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    api_prompt = workflow_to_prompt(
        wf, prompt_text, ref_images,
        custom_seed=custom_seed,
        custom_length=length_frames,
        width=768, height=1344  # 9:16 vertical 768p
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
    log(f'Found: {src}')

    # Copy video
    video_dst = output_dir / f'{slug}.mp4'
    shutil.copy2(str(src), str(video_dst))
    log(f'  video: {video_dst}')

    # Extract first frame
    frame_dst = output_dir / f'{slug}_FRAME.png'
    extract_first_frame(video_dst, frame_dst)
    log(f'  frame: {frame_dst} ({frame_dst.stat().st_size/1024:.1f}KB)')

    return frame_dst


def main():
    out_root = Path(r'E:\Minimax-H3\ceo_mindread_ep01\01_reference')

    # Phase 1: Generate character references
    # We need a stable base reference first. Use existing test image as starter.

    # Strategy: We'll use existing test images from the project as starter refs
    # to lock character identity, then iterate

    # The user has already loaded test images:
    # - example.png
    # - red_superboy_on_city_roof.png
    # - mecha_dragon_lightning.png

    # For CEO: We'll generate from scratch using a generic R2V prompt that
    # describes the CEO character + use one of the existing images as visual
    # style anchor

    # CEO Reference Generation (front-facing portrait)
    ceo_prompt = """Use <Picture 1> as a visual style anchor.
A photorealistic cinematic portrait of a 31-year-old handsome Chinese man CEO.
Lean masculine face, defined jawline, straight eyebrows, deep dark eyes,
short neatly styled black hair, clean-shaven, natural fair skin,
calm restrained expression, intelligent eyes, subtle intimidating presence.

Wearing a tailored black business suit, white dress shirt, dark charcoal tie,
silver wristwatch visible on wrist.

Premium modern corporate office background with floor-to-ceiling windows,
subtle city skyline visible, dark wood executive desk,
large modern circular glass and metal pendant light visible above the desk area.

Shot: front-facing portrait, soft natural skin texture, cinematic lighting,
professional corporate headshot style, photorealistic, vertical 9:16 composition."""

    ceo_dir = out_root / 'ceo'
    log(f'\n>>> Generating CEO reference')
    ceo_ref = gen_reference(
        'CEO_01',
        ceo_prompt,
        ref_images={'0': 'red_superboy_on_city_roof.png'},  # Use existing as visual anchor
        output_dir=ceo_dir,
        custom_seed=11111,
        length_frames=21,  # 0.875s
    )

    # INTERN Reference Generation
    intern_prompt = """Use <Picture 1> as a visual style anchor.
A photorealistic cinematic portrait of a 23-year-old beautiful Chinese woman intern.
Oval face, natural delicate facial features, large dark brown eyes,
straight shoulder-length black hair, soft bangs, natural skin texture,
slim figure, gentle intelligent appearance.

Wearing a white office blouse, light gray fitted office skirt,
simple employee badge on chest, small silver earrings.

Premium modern corporate office background with floor-to-ceiling windows,
subtle city skyline visible, dark wood executive desk,
large modern circular glass and metal pendant light visible above the desk area.

Shot: front-facing portrait, soft natural skin texture, cinematic lighting,
professional corporate headshot style, photorealistic, vertical 9:16 composition."""

    intern_dir = out_root / 'intern'
    log(f'\n>>> Generating INTERN reference')
    intern_ref = gen_reference(
        'INTERN_01',
        intern_prompt,
        ref_images={'0': 'mecha_dragon_lightning.png'},  # Use existing as visual anchor
        output_dir=intern_dir,
        custom_seed=22222,
        length_frames=21,
    )

    log('\n=== Reference Generation Phase 1 Complete ===')
    if ceo_ref:
        log(f'CEO frame: {ceo_ref}')
    if intern_ref:
        log(f'INTERN frame: {intern_ref}')


if __name__ == '__main__':
    main()