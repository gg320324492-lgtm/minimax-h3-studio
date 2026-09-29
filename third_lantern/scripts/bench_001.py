"""Benchmark Shot 001 - acting experiment per ChatGPT's protocol.

Pipeline: DRAFT (Ref2VA, 4-beat structured prompt) -> extract KF0/KF1/KF2/KF3
from frames 0/48/96/140 -> Run A (guides @0,@140) -> Run C (guides @0,48,96,140).

Both runs: camera locked, 141 frames @1344x768, 20 steps, no LoRA, no dialogue,
ref_image_size=match. Run B (real-human motion reference) awaits the user's clip.
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER = 'http://127.0.0.1:8188'
PROJECT = Path(r'E:/Minimax-H3/third_lantern')
R2V_WORKFLOW = Path(r'E:/Minimax-H3/video_minimax_h3_r2v.json')
COMFY_INPUT = Path(r'E:/ComfyUI/input')
COMFY_OUTPUT = Path(r'E:/ComfyUI/output')
BENCH = PROJECT / '10_benchmark'
FFPROBE = r'E:/Minimax-H3/tools/ffmpeg-7.1.1-full_build/bin/ffprobe.exe'
FFMPEG = r'E:/Minimax-H3/tools/ffmpeg-7.1.1-full_build/bin/ffmpeg.exe'

W, H, FPS, STEPS = 1344, 768, 24, 20
LENGTH = 141

PROMPT = """subject_definitions:

<Subject 1> is A-Ning, the young woman whose appearance, facial features, hairstyle, clothing design, and color palette come from <Picture 1>. She has a slender face, dark tied-back hair, restrained expressions, pale grey-blue traditional clothing, and a muted red apron.

<Subject 2> is Xiao-Man, the young boy whose appearance, facial features, wet dark hair, small body proportions, worn grey-blue clothing, and pale complexion come from <Picture 2>.

<Subject 3> is the lantern-shop doorway environment and the 2D Chinese hand-painted visual style from <Picture 3>: warm amber lantern light inside the shop, cool blue-grey rainy night outside, dark wooden door frame, wet stone pavement, restrained cel-style character rendering, ink-textured background painting.

<Picture 4> is the target composition at frame 0, defining the opening pose, subject placement, camera angle and doorway composition.

<Picture 5> is the target intermediate keyframe, defining the boy's partially raised hand and the woman's beginning downward gaze.

<Picture 6> is the target intermediate keyframe, defining the fully visible coin and the woman's recognition reaction.

<Picture 7> is the target final keyframe, defining the final eye contact and restrained emotional state.


summary:

[reference generation + keyframe completion] Create one continuous approximately 5.88-second 2D hand-painted Chinese supernatural-drama shot. Preserve the identities of <Subject 1> and <Subject 2> and the environment and visual treatment of <Subject 3>. Follow the four keyframe compositions from <Picture 4> through <Picture 7> without cuts.


retention_analysis:

<Subject 1> is fully preserved for A-Ning's facial identity, hairstyle, clothing design and body proportions; her pose, gaze and expression change according to the target performance.

<Subject 2> is fully preserved for Xiao-Man's facial identity, hairstyle, clothing and childlike body proportions; his arm, hand, gaze and posture follow the target performance.

<Subject 3> is fully preserved for visual style, color relationship and core doorway environment. Minor lantern flame, cloth and rain motion may occur naturally.

<Picture 4> is preserved as the opening frame composition.

<Picture 5> is used as the intermediate pose and gaze anchor around frame 48.

<Picture 6> is used as the intermediate recognition anchor around frame 96.

<Picture 7> is preserved as the final pose, gaze relationship and composition around frame 140.


detailed_description:

[Shot 1] 2D Chinese hand-painted supernatural drama animation with restrained cel-shaded characters and an ink-textured background. A medium two-shot from inside the lantern shop frames <Subject 1> on the left in warm amber interior light and <Subject 2> on the right beyond the wooden doorway in cool blue-grey rainy night light. The doorway remains a strong vertical divider between them. The camera stays completely locked; there is no camera movement of any kind.

At 00:00.000, the composition matches <Picture 4>. <Subject 1> looks directly at <Subject 2>'s face with restrained caution. <Subject 2> stands quietly with his right hand held close to his body. Both characters breathe naturally. His damp fringe barely moves, and a faint drop of water falls from the edge of his clothing.

From 00:01.100 to 00:02.000, <Subject 2> lowers his eyes first. His right shoulder shifts subtly before his forearm begins to rise. His movement is hesitant rather than mechanical. <Subject 1> initially keeps looking at his face.

Around 00:02.000, the pose approaches <Picture 5>. <Subject 2>'s right hand has risen between waist and chest level. His fingers begin to uncurl, but the coin is only partly visible. <Subject 1>'s eyes begin to move downward toward the hand a fraction before her head follows.

From 00:02.000 to 00:04.000, <Subject 2> slowly opens his palm. The old coin becomes fully visible without being pushed toward the camera. <Subject 1>'s gaze follows the hand and settles on the coin. Her brows remain controlled; her lips part slightly. Her reaction is delayed and internal rather than exaggerated.

Around 00:04.000, the composition and acting state approach <Picture 6>. <Subject 2> holds the open palm steady. <Subject 1> freezes for a brief beat after recognizing the coin. Her breathing momentarily stops. The fingers of the hand holding her lantern tighten slightly.

From 00:04.000 to 00:05.875, <Subject 1> raises her eyes from the coin back to <Subject 2>'s face. Her eyes widen only subtly and become slightly wet, with no crying. Her wrist trembles once, making the lantern tilt by only a few degrees; the hanging tassel follows with a small delayed secondary swing. <Subject 2> lifts his eyes to meet hers while keeping the coin resting in his open palm. Both characters then become still.

At the end, the framing, gaze relationship, restrained expression, hand position and composition settle into <Picture 7>. The final feeling is recognition, not fear. Avoid exaggerated acting, large camera movement, random body motion, floating limbs, hand deformation, lip movement, or unnecessary environmental motion.


overall_soundscape:

Soft rain continues outside the doorway with occasional water drops striking the stone pavement. Quiet room tone and a faint paper-lantern rustle are heard inside the shop. Cloth shifts softly as the boy raises his arm; when his palm fully opens, the old coin makes one very small metallic contact against his skin. A-Ning's breath becomes briefly audible at the moment of recognition.


non_diegetic_music:

N/A"""

REFS = ['lz3_kf2_anning_sheet.png', 'lz3_kf3_xiaoman_sheet.png', 'lz3_kf5_shop_interior.png']


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def api(path, data=None, timeout=14400):
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


def build_graph(guides, seed, prefix):
    """guides: list of (image_filename, frame_idx)."""
    wf = json.loads(R2V_WORKFLOW.read_text(encoding='utf-8'))
    link_map = {l[0]: (l[1], l[2]) for l in wf.get('links', [])}
    SKIP = {'MarkdownNote', 'Note', 'Reroute'}
    graph = {}
    for nd in wf.get('nodes', []):
        if nd.get('type') in SKIP:
            continue
        nid = str(nd['id'])
        inputs = {}
        inputs.update(nd.get('widgets_values_named') or {})
        names = nd.get('widgets_names') or []
        values = nd.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]
        if nid == '136':
            inputs['length'] = LENGTH
            inputs['noise_seed'] = seed
            inputs['prompt'] = PROMPT
            inputs['width'] = W
            inputs['height'] = H
            inputs['ref_image_size'] = 'match'
        if nid == '138':
            inputs['value'] = PROMPT
        if nid == '132':
            inputs['value'] = LENGTH / 24.0
        for inp in (nd.get('inputs') or []):
            lid, name = inp.get('link'), inp.get('name')
            if lid is None or name is None or name in inputs:
                continue
            if lid in link_map:
                src_id, src_slot = link_map[lid]
                inputs[name] = [str(src_id), src_slot]
        graph[nid] = {'class_type': nd['type'], 'inputs': inputs}

    for nid, nd in graph.items():
        ct = nd['class_type']
        if ct == 'BasicScheduler':
            nd['inputs']['steps'] = STEPS
            nd['inputs']['scheduler'] = 'beta'
        elif ct == 'LoraLoaderModelOnly':
            nd['inputs']['strength_model'] = 0.0
        elif ct == 'SaveVideo':
            nd['inputs']['filename_prefix'] = prefix
        elif ct == 'MiniMaxH3ReferenceToVideo':
            nd['inputs'].pop('ref_videos.ref_video_0', None)
            nd['inputs'].pop('ref_video_audios.ref_video_audio_0', None)
            nd['inputs'].pop('ref_audios.ref_audio_0', None)

    # wire the three picture refs explicitly
    for i, ref in enumerate(REFS):
        graph['136']['inputs'][f'ref_images.ref_image_{i}'] = [str(300 + i), 0]
        graph[str(300 + i)] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}

    # AddGuide chain for keyframes
    if guides:
        prev = '136'
        for gi, (fname, fidx) in enumerate(guides):
            gid = f'40{gi}'
            graph[f'50{gi}'] = {'class_type': 'LoadImage', 'inputs': {'image': fname}}
            graph[gid] = {'class_type': 'MiniMaxH3AddGuide', 'inputs': {
                'positive': [prev, 0], 'latent': ['136', 1], 'vae': ['119', 0],
                'image': [f'50{gi}', 0], 'frame_idx': fidx}}
            prev = gid
        graph['126']['inputs']['conditioning'] = [prev, 0]
    return graph


def submit_and_wait(graph, tag):
    resp = api('/prompt', {'prompt': graph})
    if 'prompt_id' not in resp:
        raise RuntimeError(f'submit error: {json.dumps(resp)[:1200]}')
    pid = resp['prompt_id']
    log(f'{tag}: submitted {pid}')
    t0 = time.time()
    while True:
        h = api(f'/history/{pid}')
        if pid in h:
            rec = h[pid]
            st = rec.get('status', {})
            if st.get('status_str') in ('error', 'failed'):
                raise RuntimeError(f'FAILED: {str(st.get("messages"))[-800:]}')
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
    src = next((c for c in found if c.exists()), None)
    if src is None:
        raise RuntimeError(f'{tag}: no output')
    dst = BENCH / f'{tag}.mp4'
    shutil.copy2(src, dst)
    log(f'{tag}: done in {(time.time()-t0)/60:.1f} min -> {dst.name}')
    return dst


def extract_frames(mp4, frames, out_prefix):
    for f in frames:
        out = BENCH / f'{out_prefix}_f{f:03d}.png'
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(mp4),
                        '-vf', f"select='eq(n\\,{f})',setpts=PTS-STARTPTS",
                        '-frames:v', '1', str(out)], check=True)


def main():
    BENCH.mkdir(parents=True, exist_ok=True)
    for ref in REFS + ['lz3_kf9_two_shot.png']:
        src = COMFY_INPUT / ref
        if not src.exists():
            base = ref[4:]
            shutil.copy2(PROJECT / '00_art' / base, src)

    only = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if only in ('all', 'draft'):
        draft = submit_and_wait(build_graph([], 411080, 'lz3_bench_draft'), 'draft')
        extract_frames(draft, [0, 48, 96, 140], 'KF')
        for i, f in enumerate([0, 48, 96, 140]):
            shutil.copy2(BENCH / f'KF_f{f:03d}.png', COMFY_INPUT / f'lz3_bench_KF{i}.png')
        log('draft + KF extraction done')

    if only in ('all', 'runA'):
        submit_and_wait(build_graph([('lz3_bench_KF0.png', 0),
                                     ('lz3_bench_KF3.png', 140)], 411081,
                                    'lz3_bench_runA'), 'runA')

    if only in ('all', 'runC'):
        submit_and_wait(build_graph([('lz3_bench_KF0.png', 0),
                                     ('lz3_bench_KF1.png', 48),
                                     ('lz3_bench_KF2.png', 96),
                                     ('lz3_bench_KF3.png', 140)], 411082,
                                    'lz3_bench_runC'), 'runC')

    log('benchmark generation complete')


if __name__ == '__main__':
    main()
