"""Performance upgrade for 8 character shots of《第三盏灯》.

Per-shot: DRAFT (structured 6-part prompt with observable behavior beats)
-> extract keyframes at anchor frames -> guided re-run (Run-A recipe:
first+last for <=8s, first+mid+last for longer). Camera locked everywhere.
Outputs land in 03_video_raw_upgrade/<SID>/<SID>_T768.mp4 (same lengths as
the delivered cut, so timeline/audio stay valid).
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
UP = PROJECT / '03_video_raw_upgrade'
FFMPEG = r'E:/Minimax-H3/tools/ffmpeg-7.1.1-full_build/bin/ffmpeg.exe'

W, H, FPS, STEPS = 1344, 768, 24, 20

SUBJECTS = """subject_definitions:

<Subject 1> is A-Ning, the young woman whose appearance, facial features, hairstyle, clothing design, and color palette come from <Picture 1>. She has a slender face, dark tied-back hair, restrained expressions, pale grey-blue traditional clothing, and a muted red apron.

<Subject 2> is Xiao-Man, the young boy whose appearance, facial features, wet dark hair, small body proportions, worn grey-blue clothing, and pale complexion come from <Picture 2>.

{subject3}

{pic_lines}"""

TAIL = """

retention_analysis:

<Subject 1> is fully preserved for A-Ning's facial identity, hairstyle, clothing design and body proportions; her pose, gaze and expression change according to the target performance.

<Subject 2> is fully preserved for Xiao-Man's facial identity, hairstyle, clothing and childlike body proportions; his arm, hand, gaze and posture follow the target performance.

<Subject 3> is fully preserved for visual style, color relationship and core environment. Minor lantern flame, cloth, mist and rain motion may occur naturally.

{pic_retention}

summary:

[reference generation + keyframe completion] Create one continuous 2D hand-painted Chinese supernatural-drama shot of exactly {duration:.2f} seconds. Preserve the identities of <Subject 1> and <Subject 2> and the environment and visual treatment of <Subject 3>. Follow the keyframe compositions without cuts.

detailed_description:

{description}

overall_soundscape:

{soundscape}

non_diegetic_music:

N/A"""

SOUNDS_RAIN = 'Soft rain continues outside with occasional drops striking wet stone. Quiet night air, faint paper-lantern rustle, soft cloth shifts.'
SOUNDS_RIVER = 'Quiet river water lapping the stone steps, thin mist moving, faint wind through willow branches, soft cloth shifts.'
SOUNDS_DAWN = 'Faint early birdsong, quiet street waking, soft wooden door sound, gentle room tone.'


def shot_prompt(subject3, kf_defs, pic_retention, duration, description, soundscape):
    pic_lines = '\n'.join(kf_defs)
    body = SUBJECTS.format(subject3=subject3, pic_lines=pic_lines)
    return body + TAIL.format(pic_retention=pic_retention, duration=duration,
                              description=description, soundscape=soundscape)


SHOTS = {
    'S08': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf5_shop_interior.png'],
        'len': 192, 'seed': 412008, 'kf_frames': [0, 96, 191],
        'subject3': ('<Subject 3> is the lantern-shop doorway environment and the 2D Chinese '
                     'hand-painted visual style from <Picture 3>: warm amber lantern light inside '
                     'the shop, cool blue-grey rainy night outside, dark wooden door frame, wet '
                     'stone pavement, restrained cel-style characters, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the boy stands beyond the doorway, right hand held close to his body; the woman watches his face with restrained caution.',
            '<Picture 5> is the target intermediate keyframe at frame 96: his open palm reveals the old coin; her gaze has settled on the coin, lips slightly parted.',
            '<Picture 6> is the target final keyframe at frame 191: eyes meet again over the open palm; her lantern hand trembles slightly, eyes subtly wet.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'recognition anchor near frame 96. <Picture 6> as the final pose and '
                          'gaze relationship at the last frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama, restrained cel-shaded characters, ink-textured background. Medium two-shot from inside the lantern shop: the woman on the left in warm amber light, the boy on the right beyond the doorway in cool blue-grey rainy night. The camera stays completely locked.

At 00:00.000, the woman looks at the boy's face with quiet caution; he stands still, right hand close to his body. Both breathe naturally.

From 00:01.500 to 00:03.000, the boy lowers his eyes; his right shoulder shifts subtly before the forearm rises. The woman keeps watching his face at first.

Around 00:04.000, his fingers uncurl one by one; the already-held old coin becomes visible in the open palm - it never materializes or changes size. Her eyes move down toward the hand a fraction before her head follows.

At 00:05.500, she freezes for a beat: breathing pauses, lips part slightly, the fingers holding her lantern tighten.

From 00:06.000 to 00:08.000, she raises her eyes back to his face; eyes subtly wet, no crying. Her wrist trembles once, tilting the lantern a few degrees, tassel lagging behind. He lifts his eyes to meet hers, coin resting in the open palm. Both become still. Avoid exaggerated acting, camera movement, floating limbs, lip movement.""",
        'sounds': SOUNDS_RAIN,
    },
    'S09': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf5_shop_interior.png'],
        'len': 192, 'seed': 412009, 'kf_frames': [0, 96, 191],
        'subject3': ('<Subject 3> is the lantern-shop interior and the 2D Chinese hand-painted '
                     'style from <Picture 3>: wooden counters, rows of paper lanterns, one old '
                     'BLUE paper lamp among them, warm amber light against deep blue-grey '
                     'shadow, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the woman reaches up toward the blue paper lamp hanging on the wall hook; the boy stands a step behind watching.',
            '<Picture 5> is the target intermediate keyframe at frame 96: she holds the blue lamp with both hands at chest height, lighting the wick; warm light begins to bloom.',
            '<Picture 6> is the target final keyframe at frame 191: the blue lamp glows between them; both faces lit from below; she glances at the boy.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'lighting anchor near frame 96. <Picture 6> as the final two-shot at '
                          'the last frame. The lamp stays blue in every frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama, interior of the old lantern shop at night. Medium two-shot, camera completely locked.

At 00:00.000, the woman rises on her toes and reaches both hands toward the old BLUE paper lamp on its wall hook; the boy watches from one step behind, quiet.

From 00:01.500 to 00:03.000, she unhooks the lamp and brings it down to chest height, holding it with both hands.

From 00:03.000 to 00:05.000, she lights the wick with a small flame; the lamp glows from within, warm light blooming across her face and the boy's face.

From 00:05.000 to 00:08.000, the boy's features grow clearer in the lamplight yet keep a faint misty quality, as if seen through water. She turns her head and glances at him for a moment, then looks back at the lamp. Both become still. Avoid camera movement, lip movement, exaggerated acting.""",
        'sounds': 'Quiet room tone, paper lamp surfaces rustling softly, the small flame catching, faint rain outside.',
    },
    'S10': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf6_shop_alley.png'],
        'len': 209, 'seed': 412010, 'kf_frames': [0, 104, 208],
        'subject3': ('<Subject 3> is the rain-soaked old-town alley at night and the 2D Chinese '
                     'hand-painted style from <Picture 3>: wet reflecting stone slabs, white '
                     'walls and grey tiles, swaying red lanterns, blue-grey darkness, ink-textured '
                     'backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the boy steps out of the warm doorway into the alley holding the blue lamp; the woman follows with her own warm lamp.',
            '<Picture 5> is the target intermediate keyframe at frame 104: they walk one behind the other down the alley, the boy ahead, small and quiet; long shadows stretch on the wet stone.',
            '<Picture 6> is the target final keyframe at frame 208: seen from behind, the two small figures and their two lamps move deeper into the alley toward the mist.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'walking anchor near frame 104. <Picture 6> as the final deeper-into-'
                          'alley composition at the last frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. A locked wide shot looking down the rain-soaked alley; the camera never moves - the figures walk through the frame.

At 00:00.000, the boy steps beyond the doorway holding the blue paper lamp; the woman lifts her own warm lamp and follows.

From 00:01.000 to 00:04.000, they walk away from the camera, one behind the other, his steps light and almost soundless, her pace half a beat slower, keeping a few steps of distance.

From 00:04.000 to 00:08.700, their figures grow smaller toward the misty end of the alley; long shadows stretch and waver across the wet stone; a red lantern sways once in the wind. Both keep walking steadily, neither looking back. Avoid camera movement, running, or looking at the lens.""",
        'sounds': 'Soft footsteps on wet stone, night wind, a distant wind chime, lamp frames creaking faintly.',
    },
    'S11': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf7_river.png'],
        'len': 192, 'seed': 412011, 'kf_frames': [0, 96, 191],
        'subject3': ('<Subject 3> is the night riverbank of the old town and the 2D Chinese '
                     'hand-painted style from <Picture 3>: black mirror-calm water, thin mist, '
                     'willow branches, stone steps, a distant arched bridge, grey-blue palette '
                     'with one warm lamp as the only warmth, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the two small figures enter the riverbank from the alley mouth, lamps glowing.',
            '<Picture 5> is the target intermediate keyframe at frame 96: the boy has stopped at the water edge, the blue lamp in his hand; he begins to turn his head back.',
            '<Picture 6> is the target final keyframe at frame 191: he looks back at her fully; she stands a few steps away, her lamp light trembling; mist drifts between them.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'stopping-and-turning anchor near frame 96. <Picture 6> as the final '
                          'looking-back composition at the last frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. Locked wide shot of the night riverbank; the camera never moves.

At 00:00.000, the two small figures enter from the alley mouth and walk toward the water edge, lamps glowing warm against the grey-blue night.

From 00:02.500 to 00:04.000, the boy reaches the stone steps by the water and stops, the blue lamp hanging from his hand.

From 00:04.000 to 00:05.500, he slowly turns his head back over his shoulder to look at her.

From 00:05.500 to 00:08.000, she stops a few steps behind, her lamp light trembling slightly with her breath. Mist drifts between the two figures. The black water barely reflects the lights. Both become still, facing each other across the stones. Avoid camera movement, running, exaggerated gestures.""",
        'sounds': SOUNDS_RIVER,
    },
    'S13': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf7_river.png'],
        'len': 209, 'seed': 412013, 'kf_frames': [0, 104, 208],
        'subject3': ('<Subject 3> is the night riverbank and the 2D Chinese hand-painted style '
                     'from <Picture 3>: black calm water, drifting mist, cold grey-blue tones, '
                     'one warm lantern as the only warmth, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the woman stands holding her lantern, head beginning to lower; the boy waits quietly in the mist.',
            '<Picture 5> is the target intermediate keyframe at frame 104: she has sunk down to her knees on the stone step, the lantern trembling faintly in her grip; tears well but do not fall.',
            '<Picture 6> is the target final keyframe at frame 208: kneeling, head bowed, shoulders held still by control; the boy watches her from the water edge without moving.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'kneeling anchor near frame 104. <Picture 6> as the final bowed, '
                          'held-still composition at the last frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. Locked medium shot at the riverbank; the camera never moves.

At 00:00.000, the woman stands with her lantern, her head beginning to lower; the boy waits in the mist, quiet, without resentment.

From 00:01.000 to 00:04.500, her knees slowly give: she sinks down onto the stone step, the lantern tilting in her grip, its light shaking with her hand.

From 00:04.500 to 00:07.000, kneeling, she holds herself still by force of control: tears well in her eyes but do not fall, her breath unsteady, lips pressed.

From 00:07.000 to 00:08.700, she bows her head; the boy watches her from the water edge without moving. The scene settles into heavy, held silence. No wailing, no dramatic gestures, no camera movement.""",
        'sounds': SOUNDS_RIVER,
    },
    'S14': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf7_river.png'],
        'len': 226, 'seed': 412014, 'kf_frames': [0, 112, 225],
        'subject3': ('<Subject 3> is the night riverbank and the 2D Chinese hand-painted style '
                     'from <Picture 3>: black calm water, mist, the BLUE paper lamp as the '
                     'emissive center, grey-blue night with warm lamplight, ink-textured '
                     'backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the woman kneels at the water edge holding the blue paper lamp with both hands; the boy stands close, watching.',
            '<Picture 5> is the target intermediate keyframe at frame 112: the lamp rests on the black water, just released, drifting; her hands still hang in the air where it was.',
            '<Picture 6> is the target final keyframe at frame 225: she has raised one hand toward the boy, stopped in mid-air, then lowered it; the lamp drifts away along the current.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'release anchor near frame 112. <Picture 6> as the final raised-and-'
                          'lowered hand and drifting lamp at the last frame. The lamp stays blue '
                          'and lit throughout.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. Locked medium shot at the water edge; the camera never moves.

At 00:00.000, the woman kneels holding the blue paper lamp with both hands; the boy stands close, watching.

From 00:01.000 to 00:03.500, she leans forward and lowers the lamp to the black water with both hands, careful and slow.

Around 00:04.500, her fingers let go: the lamp floats, its warm glow rocking on the ripples, beginning to drift with the current.

From 00:05.500 to 00:07.500, she raises her right hand toward the boy - as if to smooth his hair one last time - and stops in mid-air; then the hand sinks back down to her lap.

From 00:07.500 to 00:09.400, the lamp drifts farther along the water, its glow shrinking; neither of them moves. Tender, restrained, no tears falling, no camera movement.""",
        'sounds': SOUNDS_RIVER,
    },
    'S15': {
        'refs': ['kf2_anning_sheet.png', 'kf3_xiaoman_sheet.png', 'kf7_river.png'],
        'len': 192, 'seed': 412015, 'kf_frames': [0, 96, 191],
        'subject3': ('<Subject 3> is the misty night riverbank and the 2D Chinese hand-painted '
                     'style from <Picture 3>: drifting mist, warm lantern glow softening into '
                     'the dark, grey-blue night, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the boy stands in the lantern glow facing the woman, his expression eased for the first time.',
            '<Picture 5> is the target intermediate keyframe at frame 96: he gives her one small clean smile, then begins to turn away into the mist.',
            '<Picture 6> is the target final keyframe at frame 191: his figure has grown faint, half-dissolved into the mist and lamplight, still walking away; she watches without moving.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the '
                          'smile-and-turn anchor near frame 96. <Picture 6> as the final '
                          'fading-into-mist composition at the last frame.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. Locked medium shot in riverbank mist; the camera never moves.

At 00:00.000, the boy stands inside the soft lantern glow, facing the woman; his shoulders ease and his expression relaxes for the first time.

From 00:02.000 to 00:04.000, he gives her one small, clean smile - brief and weightless.

From 00:04.000 to 00:08.000, he turns and walks into the mist, away from her; his outline thins gradually, half-dissolving into the glow and fog, never vanishing abruptly. The woman stays exactly where she is, watching, without moving. Gentle, quiet, like someone finally finding his way home. Avoid horror effects, sudden disappearance, camera movement.""",
        'sounds': 'Muffled water, thin wind, the paper lamp creaking once, footsteps fading into soft mist.',
    },
    'S16': {
        'refs': ['kf1_anning_portrait.png', 'kf5_shop_interior.png'],
        'len': 192, 'seed': 412916, 'kf_frames': [0, 96, 191],
        'subject3': ('<Subject 3> is the lantern-shop interior at first light and the 2D Chinese '
                     'hand-painted style from <Picture 3>: grey night giving way to pale morning, '
                     'paper lanterns dark and quiet, wooden counter, dust motes in a thin blade '
                     'of daylight, soft warm-cool transition, ink-textured backgrounds.'),
        'kf_defs': [
            '<Picture 4> is the target composition at frame 0: the woman pushes the wooden door fully open; pale morning light slides into the dim shop.',
            '<Picture 5> is the target intermediate keyframe at frame 96: on the counter lies the old copper coin, dry now; she picks it up gently.',
            '<Picture 6> is the target final keyframe at frame 191: she closes the coin inside her palm and lifts her eyes toward the open doorway and the new daylight.',
        ],
        'pic_retention': ('<Picture 4> preserved as opening composition. <Picture 5> as the coin '
                          'anchor near frame 96. <Picture 6> as the final palm-and-daylight '
                          'composition at the last frame. The coin stays a small old copper coin, '
                          'dry and still.'),
        'desc': """[Shot] 2D Chinese hand-painted supernatural drama. Locked interior shot facing the door; the camera never moves.

At 00:00.000, first pale morning light; the woman pushes the two wooden door leaves fully open, and a thin blade of daylight slides across the floor into the dim shop.

From 00:03.000 to 00:05.000, the camera-static frame reveals the counter: the old copper coin lies there, dry and quiet, no longer damp.

From 00:05.000 to 00:07.000, she picks the coin up gently with both fingers and closes it inside her palm, holding it against her chest.

From 00:07.000 to 00:08.000, she lifts her eyes and looks out through the open door toward the new daylight. Calm, released, quietly alive. No tears, no smile, no camera movement.""",
        'sounds': SOUNDS_DAWN,
    },
}


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


def build_graph(prompt, seed, length, refs, guides, prefix):
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
            inputs['length'] = length
            inputs['noise_seed'] = seed
            inputs['prompt'] = prompt
            inputs['width'] = W
            inputs['height'] = H
            inputs['ref_image_size'] = 'match'
        if nid == '138':
            inputs['value'] = prompt
        if nid == '132':
            inputs['value'] = length / 24.0
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

    for i, ref in enumerate(refs):
        graph['136']['inputs'][f'ref_images.ref_image_{i}'] = [str(300 + i), 0]
        graph[str(300 + i)] = {'class_type': 'LoadImage', 'inputs': {'image': ref}}

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
    return src, time.time() - t0


def extract_frames(mp4, frames, out_dir, prefix):
    outs = []
    for f in frames:
        out = out_dir / f'{prefix}_f{f:03d}.png'
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', str(mp4),
                        '-vf', f"select='eq(n\\,{f})',setpts=PTS-STARTPTS",
                        '-frames:v', '1', str(out)], check=True)
        outs.append(out)
    return outs


def upgrade(sid):
    spec = SHOTS[sid]
    length = spec['len']
    duration = length / FPS
    refs = []
    for r in spec['refs']:
        name = f'lz3_{r}'
        src = COMFY_INPUT / name
        if not src.exists() or src.stat().st_size != (PROJECT / '00_art' / r).stat().st_size:
            shutil.copy2(PROJECT / '00_art' / r, src)
        refs.append(name)

    out_dir = UP / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f'{sid}_T768.mp4'
    if final.exists() and final.stat().st_size > 300_000:
        log(f'SKIP {sid} (exists)')
        return final

    prompt = shot_prompt(spec['subject3'], spec['kf_defs'], spec['pic_retention'],
                         duration, spec['desc'], spec['sounds'])

    draft = out_dir / f'{sid}_draft.mp4'
    if not draft.exists() or draft.stat().st_size < 300_000:
        draft_name = f'lz3_up_{sid}_draft'
        draft_src, wall = submit_and_wait(build_graph(prompt, spec['seed'], length, refs,
                                                      [], draft_name), f'{sid} draft')
        shutil.copy2(draft_src, draft)
        log(f'{sid}: draft done in {wall:.0f}s')
    else:
        log(f'{sid}: draft exists, skip')

    kfs = extract_frames(draft, spec['kf_frames'], out_dir, f'{sid}_KF')
    guides = []
    for kf, fidx in zip(kfs, spec['kf_frames']):
        gname = f'lz3_up_{sid}_KF{fidx}.png'
        shutil.copy2(kf, COMFY_INPUT / gname)
        guides.append((gname, fidx))

    run_seed = spec['seed'] + 500
    src, wall = submit_and_wait(build_graph(prompt, run_seed, length, refs, guides,
                                            f'lz3_up_{sid}'), f'{sid} guided')
    shutil.copy2(src, final)
    log(f'{sid}: guided done in {wall:.0f}s -> {final.name}')
    return final


def main():
    only = sys.argv[1:] or list(SHOTS)
    t0 = time.time()
    for sid in only:
        upgrade(sid)
    log(f'ALL DONE in {(time.time()-t0)/60:.1f} min')


if __name__ == '__main__':
    main()
