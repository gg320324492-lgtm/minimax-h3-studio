"""P6: Generate 8 reference sheets per character via R2V (21-frame clips -> first frame).

CEO:  01 front / 02 45L / 03 45R / 04 half-body / 05 seated / 06 standing / 07 stern / 08 shocked
INTERN: 01 front / 02 45L / 03 45R / 04 half-body / 05 smile / 06 nervous / 07 shocked / 08 afraid
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
import subprocess
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
PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')


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
    """Deprecated -- kept only so old callers fail loudly instead of silently.

    Newest-mtime guessing returns the wrong clip whenever any other job writes
    to ComfyUI/output. Use comfy_utils.resolve_output_file(rec) instead.
    """
    raise RuntimeError(
        'find_latest_video() is unsafe (mtime guessing). '
        'Use comfy_utils.resolve_output_file(rec) with the /history record.')


def gen_ref(slug, prompt, ref_image, out_dir, seed):
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f'{slug}.png'
    if png.exists():
        log(f'  SKIP {slug}')
        return png
    wf = json.loads(WORKFLOW.read_text(encoding='utf-8'))
    api_prompt = workflow_to_prompt(wf, prompt, {'0': ref_image}, seed, 21, 768, 1344)
    resp = api('/prompt', method='POST', data={'prompt': api_prompt})
    if 'error' in resp:
        log(f'  ERROR {slug}: {resp["error"]["message"][:120]}')
        return None
    pid = resp['prompt_id']
    rec = None
    # P0.3: bounded polling (was an unbounded while-True loop; R3)
    rec = wait_for_prompt(api, pid, deadline_s=DEADLINE_S, log=log)
    if rec is None:
        return None
    src = resolve_output_file(rec or {})
    if not src:
        log(f'  No output found for {slug}!')
        return None
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
                    '-frames:v', '1', str(png)], check=True)
    log(f'  saved {png.name}')
    return png


CEO_BASE = """Use <Picture 1> as the exact same person: a 31-year-old handsome Chinese male CEO, lean masculine face, defined jawline, straight eyebrows, deep dark eyes, short neatly styled black hair, clean-shaven, wearing a tailored black business suit, white dress shirt, dark charcoal tie, silver wristwatch. Premium Chinese executive office with circular pendant light and city skyline through windows. Photorealistic, cinematic, vertical 9:16 composition. """

INTERN_BASE = """Use <Picture 1> as the exact same person: a 23-year-old beautiful Chinese woman office intern, oval face, large dark brown eyes, straight shoulder-length black hair with soft bangs, wearing a white office blouse with neck bow, light gray fitted skirt, employee badge, small silver earrings. Premium Chinese executive office with circular pendant light and city skyline through windows. Photorealistic, cinematic, vertical 9:16 composition. """

POSES = {
    '01_front':    'Front-facing portrait, looking directly at camera, neutral calm expression, head-and-shoulders framing.',
    '02_45L':      'Portrait with head turned 45 degrees to her/his left, neutral expression, head-and-shoulders framing.',
    '03_45R':      'Portrait with head turned 45 degrees to her/his right, neutral expression, head-and-shoulders framing.',
    '04_halfbody': 'Half-body shot at slight angle, hands naturally relaxed, neutral expression.',
    '_CEO_05_seated':  'Seated behind the executive desk in the leather chair, hands on desk, calm dominant posture.',
    '_CEO_06_standing': 'Full-body standing shot beside the desk, composed posture.',
    '_CEO_07_stern':   'Close-up with stern, coldly analytical expression, slight frown, piercing gaze.',
    '_CEO_08_shocked': 'Close-up with shocked alert expression, eyes widened, mouth slightly open.',
    '_INT_05_smile':    'Half-body shot with a gentle warm polite smile, slightly shy.',
    '_INT_06_nervous':  'Close-up with nervous anxious expression, biting lip slightly, tense eyes.',
    '_INT_07_shocked':  'Close-up with shocked expression, eyes wide, hands raised slightly.',
    '_INT_08_afraid':   'Extreme close-up with afraid fearful expression, trembling, tears welling.',
}

SHEETS = []
for k in ['01_front', '02_45L', '03_45R', '04_halfbody']:
    SHEETS.append(('ceo', f'CEO_{k}', CEO_BASE + POSES[k]))
SHEETS += [
    ('ceo', 'CEO_05_seated',   CEO_BASE + POSES['_CEO_05_seated']),
    ('ceo', 'CEO_06_standing', CEO_BASE + POSES['_CEO_06_standing']),
    ('ceo', 'CEO_07_stern',    CEO_BASE + POSES['_CEO_07_stern']),
    ('ceo', 'CEO_08_shocked',  CEO_BASE + POSES['_CEO_08_shocked']),
]
for k in ['01_front', '02_45L', '03_45R', '04_halfbody']:
    SHEETS.append(('intern', f'INTERN_{k}', INTERN_BASE + POSES[k]))
SHEETS += [
    ('intern', 'INTERN_05_smile',   INTERN_BASE + POSES['_INT_05_smile']),
    ('intern', 'INTERN_06_nervous', INTERN_BASE + POSES['_INT_06_nervous']),
    ('intern', 'INTERN_07_shocked', INTERN_BASE + POSES['_INT_07_shocked']),
    ('intern', 'INTERN_08_afraid',  INTERN_BASE + POSES['_INT_08_afraid']),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    t0 = time.time()
    done = 0
    # Seed comes from the sheet's position in SHEETS, not from a running
    # success counter. The old `71000 + done * 37` shifted every downstream
    # seed whenever you ran a subset (`only=CEO_05`) or resumed after a
    # failure, so the same sheet got a different face on a filtered re-run.
    for idx, (character, slug, prompt) in enumerate(SHEETS):
        if only != 'all' and only not in slug:
            continue
        out_dir = PROJECT / f'01_reference/{character}'
        ref = 'CEO_MASTER_REFERENCE.png' if character == 'ceo' else 'INTERN_MASTER_REFERENCE.png'
        seed = 71000 + idx * 37
        if gen_ref(slug, prompt, ref, out_dir, seed):
            done += 1
    log(f'\n=== Reference sheets: {done} generated in {(time.time()-t0)/60:.1f} min ===')


if __name__ == '__main__':
    main()
