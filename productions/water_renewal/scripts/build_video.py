"""Build the 123s promo timeline 《让水体重新呼吸》.

Pass 1  normalize photos (EXIF transpose -> work/norm)
Pass 2  render each scene (Ken Burns stills / video cuts / H3 clips), no text
Pass 3  concat scenes with 0.5s dissolves
Pass 4  burn drawtext layer (big words, chips, 原理示意, end card) + ASS captions
Pass 5  audio mix (narration bus + ducked BGM + ambience beds), mux, loudnorm

Run:  python build_video.py [scene|concat|overlay|audio|all]
"""
import json
import shutil
import subprocess
import sys
import concurrent.futures as cf
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
    sys.path.insert(0, r'E:\Minimax-H3\scripts')
from ffmpeg_env import prepend_to_path as _p  # noqa: E402
_p()

SRC = Path(r'C:/Users/pc/Desktop/黑臭水体治理宣传视频')
ROOT = Path(r'E:/promo_video')
A = ROOT / 'assets'
W = ROOT / 'work' / 'build'
SC = W / 'scenes'
OUT = ROOT / 'output'
for d in (W, SC, OUT):
    d.mkdir(parents=True, exist_ok=True)

FPS = 30
XF = 0.5
LEAD, TAIL = 0.8, 1.0   # GAP between narration lines is forced to LEAD+TAIL-XF = 1.3s
FONT_BD = 'C\:/Windows/Fonts/msyhbd.ttc'
FONT_RG = 'C\:/Windows/Fonts/NotoSansSC-VF.ttf'

V = {
    '4ea2': '4ea227e2e2317ab51fa610d9e711a4c3_raw.mp4',
    '8e2c': '8e2c023a88a34c9ca73d6439b2dd9465_raw.mp4',
    'dd78': 'dd78eb8b3c9dff99866c0a01dba1d800_raw.mp4',
    'a7':   '000284a734037dcc3c2061baffa75948_raw.mp4',
    'fa':   'fa5960e3c26c04392c4cdac888f8d9d9_raw.mp4',
    '1ed4': '1ed4eff7a81ab77f952731b0cd85da29_raw.mp4',
    'b51':  '51dd3920f2916597ee7938944b3972a9_raw.mp4',
    'riv':  '3938e323d52417820363a14e4c5961df_raw.mp4',
}
# photo index -> file id (sorted WeChat export order, see contact sheets)
P = {1: '257', 2: '258', 3: '260', 4: '261', 5: '262', 6: '263', 7: '264',
     8: '265', 9: '267', 10: '268', 11: '270', 12: '272', 13: '273', 14: '275',
     15: '276', 16: '278', 17: '279', 18: '280', 19: '282', 20: '283',
     21: '285', 22: '286', 23: '288', 24: '289'}

# phone-number blur regions: per user request (2026-09-22), contact info on
# the group's own equipment is shown unblurred.
BLUR = {}

# ---------------- schedule ----------------
def scene_schedule():
    """Narration-driven schedule: narration times chain with a fixed GAP, scenes
    wrap around them. Guarantees zero speech overlap (v2's N01/N02 collided)."""
    man = json.loads((ROOT / 'work' / 'narration_manifest.json').read_text(encoding='utf-8'))
    nd = {m['slug']: m['duration'] for m in man}
    GAP = LEAD + TAIL - XF                      # 1.3s of silence between lines
    narr = {1: 7.0}                             # intro plays 7s before first line
    for k in range(2, 13):
        narr[k] = round(narr[k - 1] + nd[f'N{k - 1:02d}'] + GAP, 2)
    start = {1: 0.0}
    dur = {1: round(narr[2] - LEAD + XF, 2)}    # scene 1 stretches to meet scene 2
    for k in range(2, 12):
        dur[k] = round(LEAD + nd[f'N{k:02d}'] + TAIL, 2)
        start[k] = round(narr[k] - LEAD, 2)
    start[12] = round(narr[12] - LEAD, 2)
    dur[12] = round(LEAD + nd['N12'] + TAIL + 4.5, 2)   # + end-card hold
    total = round(start[12] + dur[12], 2)
    return dur, start, narr, total

SCENES_DUR, STARTS, NARR, TOTAL = scene_schedule()

SHOTS = {
    1:  [('vid', V['4ea2'], 0.0, None), ('ph', 12, None, 'in'),
         ('ph', 10, None, 'out')],   # no black lead: WeChat thumbnails take frame 0
    2:  [('ph', 22, 2.7, 'in', 0.55), ('ph', 5, 2.7, 'out'), ('ph', 6, 2.6, 'in'),
         ('vid', V['8e2c'], 0.3, 2.7)],
    3:  [('ph', 1, 6.0, 'in'), ('ph', 2, 5.9, 'out')],
    4:  [('ph', 20, 4.2, 'in'), ('vid', V['a7'], 2.3, 2.2), ('ph', 11, 3.2, 'out')],
    5:  [('h3', 'H3A_1080.mp4', 8.0), ('ph', 9, None, 'in')],
    6:  [('ph', 13, 3.2, 'out'), ('vid', V['dd78'], 0.2, 3.3), ('ph', 7, 3.3, 'in')],
    7:  [('vid', V['b51'], 0.8, 3.8), ('ph', 16, 3.0, 'in'), ('ph', 23, 2.9, 'out')],
    8:  [('vid', V['fa'], 6.3, 2.0), ('vid', V['1ed4'], 0.4, 4.2),
         ('vid', V['fa'], 33.5, 7.1)],
    9:  [('vid', V['riv'], 0.0, 4.9), ('ph', 17, 5.1, 'in')],
    10: [('h3', 'H3B_1080.mp4', 8.0), ('ph', 8, None, 'out')],
    11: [('ph', 3, 2.0, 'in'), ('vid', V['a7'], 9.8, 2.0), ('vid', V['b51'], 6.0, 2.0),
         ('ph', 14, 2.0, 'out'), ('vid', V['fa'], 41.0, 2.0), ('ph', 15, 1.6, 'in')],
    12: [('ph', 18, SCENES_DUR[12], 'slow', 0.5, ('fadeout', 0.8, 3.8))],
}


KB_W, KB_H = 7680, 4320          # 4x supersample canvas: kills zoompan jitter
KB_VPOS = {22: 0.55}             # vertical crop position override per photo


def norm_photos():
    """EXIF-transpose sources AND bake the 7680x4320 Ken Burns canvas
    (cover-crop + phone-number blur) once per photo, so zoompan works on a
    huge pre-scaled still instead of rescaling every frame."""
    import os
    from PIL import Image, ImageOps, ImageFilter
    nd = W / 'norm'
    kd = W / 'kb'
    nd.mkdir(parents=True, exist_ok=True)
    kd.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    for idx, fid in P.items():
        src = next(f for f in files if fid in f)
        im = Image.open(SRC / src)
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((7680, 7680), Image.LANCZOS)
        sw, sh = im.size
        vpos = KB_VPOS.get(idx, 0.5)
        scale = max(KB_W / sw, KB_H / sh)
        Ws, Hs = round(sw * scale), round(sh * scale)
        x_off, y_off = (Ws - KB_W) // 2, int((Hs - KB_H) * vpos)
        canvas = im.resize((Ws, Hs), Image.LANCZOS).crop(
            (x_off, y_off, x_off + KB_W, y_off + KB_H))
        for (nx, ny, nw, nh) in BLUR.get(idx, []):
            cx, cy = int(nx * Ws) - x_off, int(ny * Hs) - y_off
            cw, ch = int(nw * Ws), int(nh * Hs)
            cx, cy = max(cx, 0), max(cy, 0)
            box = (cx, cy, min(cx + cw, KB_W), min(cy + ch, KB_H))
            region = canvas.crop(box).filter(ImageFilter.GaussianBlur(48))
            canvas.paste(region, box)
        canvas.save(kd / f'p{idx:02d}.jpg', quality=93)
        im.save(nd / f'p{idx:02d}.png')
    print('kb canvases:', len(P))


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(str(cmd[:6]) + '\n' + r.stderr[-1600:])
    return r


def kb_filter(idx, direction, nframes, vpos=0.5):
    """Smooth Ken Burns: zoompan crops/scales on the pre-baked 7680x4320
    canvas, so its integer-pixel rounding stays at ~1/4 output pixel and the
    motion reads as continuous after the downscale."""
    amp = 0.045 if direction == 'slow' else 0.06
    p = f'on/{max(nframes - 1, 1)}'
    if direction in ('in', 'slow'):
        z = f'1+{amp}*{p}'
        x = '(iw-iw/zoom)/2'
        y = '(ih-ih/zoom)/2'
    elif direction == 'out':
        z = f'1+{amp}*(1-{p})'
        x = '(iw-iw/zoom)/2'
        y = '(ih-ih/zoom)/2'
    else:  # lateral drift
        z = f'{1 + amp}'
        x = f'(iw-iw/zoom)*{p}'
        y = '(ih-ih/zoom)/2'
    vf = (f'zoompan=z={z}:x={x}:y={y}:d=1:s=1920x1080:fps={FPS},'
          f'unsharp=7:7:0.25:7:7:0.0,format=yuv420p')
    return vf


def render_shot(shot, out, dur):
    kind = shot[0]
    if kind == 'black':
        run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi',
             '-i', f'color=black:s=1920x1080:r={FPS}', '-t', f'{dur}',
             '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', str(out)])
    elif kind == 'vid':
        _, src, ss = shot[:3]
        run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{ss}', '-t', f'{dur}',
             '-i', str(SRC / src), '-vf',
             f'fps={FPS},scale=1920:1080:force_original_aspect_ratio=increase:'
             f'flags=lanczos,crop=1920:1080,eq=saturation=1.05:contrast=1.02,'
             f'format=yuv420p', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast',
             str(out)])
    elif kind == 'h3':
        _, name = shot[:2]
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(A / 'h3' / name),
             '-vf', f'fps={FPS},eq=saturation=1.03:contrast=1.03,format=yuv420p',
             '-t', f'{dur}', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', str(out)])
    elif kind == 'ph':
        _, idx, _d, direction = shot[:4]
        vpos = shot[4] if len(shot) > 4 and not isinstance(shot[4], str) else 0.5
        vf = kb_filter(idx, direction, int(dur * FPS) + 1, vpos)
        opt = shot[5] if len(shot) > 5 else None
        if opt and opt[0] == 'fadeout':
            vf += f',fade=t=out:st={opt[1]}:d={opt[2]}'
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate',
               str(FPS), '-t', f'{dur + 0.2}', '-i', str(W / 'kb' / f'p{idx:02d}.jpg'),
               '-vf', vf, '-t', f'{dur}', '-c:v', 'libx264', '-crf', '16',
               '-preset', 'fast', str(out)]
        run(cmd)


def render_scenes():
    norm_photos()
    jobs = []
    for si, shots in SHOTS.items():
        sdir = SC / f'S{si:02d}'
        sdir.mkdir(exist_ok=True)
        jobs.append((si, shots))
    def do(si_shots):
        si, shots = si_shots
        sdir = SC / f'S{si:02d}'
        dur_total = SCENES_DUR[si]
        if (sdir / 'scene.mp4').exists() and (sdir / 'scene.mp4').stat().st_size > 10000:
            print(f'scene S{si:02d} skip (exists)', flush=True)
            return
        if len(shots) == 1:
            render_shot(shots[0], sdir / 'scene.mp4', dur_total)
        else:
            # per-shot durations: given explicit or split remaining
            durs = []
            for sh in shots:
                if sh[0] in ('black', 'h3'):
                    durs.append(sh[-1])
                elif sh[0] == 'vid':
                    durs.append(sh[3])
                else:
                    durs.append(sh[2])
            n_none = sum(1 for d in durs if d is None)
            if n_none:
                fixed = sum(d for d in durs if d is not None)
                share = round((dur_total - fixed) / n_none, 2)
                durs = [share if d is None else d for d in durs]
            rem = round(dur_total - sum(durs), 2)
            if abs(rem) > 0.05:      # distribute correction on the longest shot
                k = durs.index(max(durs))
                durs[k] = round(durs[k] + rem, 2)
            parts = []
            for j, (sh, d) in enumerate(zip(shots, durs)):
                p = sdir / f'part_{j:02d}.mp4'
                render_shot(sh, p, d)
                parts.append(p)
            lst = sdir / 'list.txt'
            lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts), encoding='utf-8')
            run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                 '-i', str(lst), '-c', 'copy', str(sdir / 'scene.mp4')])
        print(f'scene S{si:02d} done ({dur_total}s)', flush=True)
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(do, jobs))


def concat():
    inputs = []
    for si in range(1, 13):
        # xfade in ffmpeg 7.1.1 mis-truncates B-frame streams; re-wrap B-free
        nobf = SC / f'S{si:02d}' / 'scene_nobf.mp4'
        if not (nobf.exists() and nobf.stat().st_size > 10000):
            run(['ffmpeg', '-y', '-loglevel', 'error',
                 '-i', str(SC / f'S{si:02d}' / 'scene.mp4'),
                 '-c:v', 'libx264', '-bf', '0', '-crf', '13', '-preset', 'fast',
                 str(nobf)])
        inputs.append(nobf)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error']
    for p in inputs:
        cmd += ['-i', str(p)]
    fc = []
    prev = '[v0]'
    off = 0.0
    for k in range(12):
        fc.append(f'[{k}:v]setpts=PTS-STARTPTS,fps={FPS}[v{k}]')
    for k in range(1, 12):
        off += SCENES_DUR[k] - XF
        nxt = f'[x{k}]' if k < 11 else '[vout]'
        fc.append(f'{prev}[v{k}]xfade=transition=fade:duration={XF}:offset={off:.3f}{nxt}')
        prev = nxt
    script = W / 'concat.txt'
    script.write_text(';\n'.join(fc), encoding='utf-8')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-filter_complex_script', str(script),
         '-map', '[vout]', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium',
         str(W / 'concat.mp4')])
    print('concat done', round(off + XF, 2), 's')


def _tf(text):
    n = W / 'tf'
    n.mkdir(exist_ok=True)
    import hashlib
    f = n / (hashlib.md5(text.encode()).hexdigest()[:10] + '.txt')
    if not f.exists():
        f.write_text(text, encoding='utf-8')
    return f


def drawtext(t0, t1, text, size, y, font=FONT_BD, fade=0.4, box=False, x='(w-text_w)/2', border=False):
    # colon-free relative paths: overlay() runs ffmpeg with cwd=work/build
    esc = 'tf/' + _tf(text).name
    fnt = 'fonts/' + Path(font.replace('\\:', ':')).name
    if box:
        # boxed chips: the box ignores the alpha expression, so hard-switch
        return (f"drawtext=fontfile={fnt}:textfile={esc}:fontsize={size}:fontcolor=white:"
                f"x={x}:y={y}:enable='between(t,{t0},{t1})'"
                f":box=1:boxcolor=black@0.42:boxborderw=14")
    a = (f"if(lt(t,{t0}),0,if(lt(t,{t0 + fade}),(t-{t0})/{fade},"
         f"if(lt(t,{t1 - fade}),1,if(lt(t,{t1}),({t1}-t)/{fade},0))))")
    extra = ':bordercolor=black@0.75:borderw=3' if border else ':shadowcolor=black@0.55:shadowx=2:shadowy=2'
    return (f"drawtext=fontfile={fnt}:textfile={esc}:fontsize={size}:fontcolor=white:"
            f"x={x}:y={y}:alpha='{a}'{extra}")


def overlay():
    fdir = W / 'fonts'
    fdir.mkdir(exist_ok=True)
    for src in ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/NotoSansSC-VF.ttf'):
        if not (fdir / Path(src).name).exists():
            shutil.copy2(src, fdir / Path(src).name)
    ev = []
    s1 = 0.0
    ev.append(drawtext(0.9, 3.3, '一条河道', 84, 'h*0.70'))
    ev.append(drawtext(3.3, 5.7, '一个现场问题', 84, 'h*0.70'))
    ev.append(drawtext(5.7, 8.0, '如何重新建立活力？', 84, 'h*0.70'))
    s2 = STARTS[2]
    ev.append(drawtext(s2 + 1.0, s2 + 5.5, '上覆水', 36, 'h-300', font=FONT_RG, box=True, x='150'))
    ev.append(drawtext(s2 + 4.2, s2 + 8.7, '底泥', 36, 'h-300', font=FONT_RG, box=True, x='150'))
    ev.append(drawtext(s2 + 5.5, s2 + 10.2, '问题，在现场。', 72, 'h*0.24'))
    ev.append(drawtext(s2 + 7.4, s2 + 10.4, '污染输入 · 水动力', 36, 'h-300', font=FONT_RG, box=True, x='150'))
    s3 = STARTS[3]
    ev.append(drawtext(s3 + 1.2, s3 + 7.5, '现场调查 · 方案论证 · 工艺设计', 38, 'h-300', font=FONT_RG, box=True, x='(w-text_w)/2'))
    ev.append(drawtext(s3 + 5.0, s3 + 11.2, '答案，也必须回到现场。', 72, 'h*0.24'))
    s4 = STARTS[4]
    ev.append(drawtext(s4 + 1.0, s4 + 6.6, '臭氧微纳米气泡一体机', 40, 'h-300', font=FONT_RG, box=True, x='150'))
    s5 = STARTS[5]
    ev.append(drawtext(s5 + 0.3, s5 + 7.9, '原理示意', 30, 'h-170', font=FONT_RG, box=True, x='w-text_w-130'))
    ev.append(drawtext(s5 + 1.2, s5 + 3.6, '微小尺度', 64, 'h*0.76'))
    ev.append(drawtext(s5 + 3.8, s5 + 6.2, '强化气液传质', 64, 'h*0.76'))
    ev.append(drawtext(s5 + 6.4, s5 + 8.2, '增强界面作用', 64, 'h*0.76'))
    s6 = STARTS[6]
    ev.append(drawtext(s6 + 1.2, s6 + 6.4, '现场清理 / 污染排查', 38, 'h-300', font=FONT_RG, box=True, x='150'))
    s7 = STARTS[7]
    ev.append(drawtext(s7 + 1.2, s7 + 6.9, '管网布设 · 参数调试 · 现场实施', 38, 'h-300', font=FONT_RG, box=True, x='(w-text_w)/2'))
    s8 = STARTS[8]
    ev.append(drawtext(s8 + 8.6, s8 + 13.0, '微纳米气泡持续运行', 38, 'h-300', font=FONT_RG, box=True, x='(w-text_w)/2'))
    s9 = STARTS[9]
    ev.append(drawtext(s9 + 4.0, s9 + 9.3, '从实验室，到真实河道。', 72, 'h*0.24'))
    s10 = STARTS[10]
    ev.append(drawtext(s10 + 0.3, s10 + 7.9, '原理示意', 30, 'h-170', font=FONT_RG, box=True, x='w-text_w-130'))
    ev.append(drawtext(s10 + 1.2, s10 + 4.8, '底泥 — 水界面', 64, 'h*0.24'))
    ev.append(drawtext(s10 + 4.9, s10 + 8.6, '污染控制 · 氧化转化', 38, 'h-300', font=FONT_RG, box=True, x='(w-text_w)/2'))
    s11 = STARTS[11]
    ev.append(drawtext(s11 + 1.0, s11 + 11.0, '机理 → 装备 → 工程验证', 64, 'h*0.78'))
    s12 = STARTS[12]
    # end card: background darkens to black (scene fade), text enters with border
    ev.append(drawtext(s12 + 2.6, TOTAL - 0.2, '从一颗微小气泡，到一条真实河道。', 74, 'h*0.40', fade=0.8, border=True))
    ev.append(drawtext(s12 + 4.6, TOTAL - 0.2, '天津大学 微纳米气泡课题组', 52, 'h*0.56', fade=0.8, border=True))
    ev.append(drawtext(s12 + 4.6, TOTAL - 0.2, 'Micro & Nano Bubble Technology Lab · mnb-lab.cn', 32, 'h*0.645', fade=0.8, border=True))
    ev.append(drawtext(s12 + 6.8, TOTAL - 0.2, '让技术，参与水环境的重新呼吸。', 44, 'h*0.775', fade=0.8, border=True))

    script = W / 'overlay.txt'
    script.write_text(','.join(ev), encoding='utf-8')
    # captions first, then the drawtext layer; both run with cwd=work/build so
    # every filter path is colon-free (filter_complex_script eats escapes)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'concat.mp4',
         '-vf', 'ass=captions.ass',
         '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', 'with_ass.mp4'],
        cwd=W)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'with_ass.mp4',
         '-filter_complex_script', 'overlay.txt', '-c:v', 'libx264', '-crf', '16',
         '-preset', 'medium', '-t', f'{TOTAL}', 'visual.mp4'], cwd=W)
    print('overlay done')


def make_ass():
    man = json.loads((ROOT / 'work' / 'narration_manifest.json').read_text(encoding='utf-8'))

    def ts(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
        return f'{h}:{m:02d}:{s:05.2f}'

    def split16(text):
        import re
        parts = [p for p in re.split(r'[，。；：、？！]', text) if p]
        out = []
        # break at a function-word boundary when a clause exceeds 16 chars,
        # never mid-word (e.g. 技术路/径 -> 技术/路径)
        BOUND = '的和与在为对把从到被把让向于上下中内'
        for p in parts:
            while len(p) > 16:
                cut = next((i for i in range(15, 7, -1)
                            if i < len(p) and p[i - 1] in BOUND), 13)
                out.append(p[:cut]); p = p[cut:]
            out.append(p)
        return out

    evs = []
    for i, m in enumerate(man, 1):
        t0 = NARR[i]
        t1 = t0 + m['duration']
        caps = split16(m['text'])
        total_chars = sum(len(c) for c in caps)
        cur = t0
        for c in caps:
            d = (t1 - t0) * len(c) / total_chars
            evs.append((cur, min(cur + d - 0.05, t1), c))
            cur += d
    lines = ['[Script Info]', 'ScriptType: v4.00+',
             'PlayResX: 1920', 'PlayResY: 1080', 'WrapStyle: 0', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Cap,Noto Sans SC,46,&H00FFFFFF,&H00FFFFFF,&H00101010,&H7F000000,0,0,0,0,100,100,0.5,0,1,1.6,1.1,2,110,110,52,1',
             '',
             '[Events]',
             'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for a, b, c in evs:
        lines.append(f'Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\fad(180,180)}}{c}')
    (W / 'captions.ass').write_text('\n'.join(lines), encoding='utf-8')
    print('ass captions:', len(evs))


def audio_mix():
    man = json.loads((ROOT / 'work' / 'narration_manifest.json').read_text(encoding='utf-8'))
    cmd = ['ffmpeg', '-y', '-loglevel', 'error']
    cmd += ['-i', str(A / 'bgm_score.wav')]                      # 0
    for m in man:                                                 # 1..12
        cmd += ['-i', m['file']]
    cmd += ['-stream_loop', '-1', '-i', str(A / 'amb_river.wav')]  # 13
    cmd += ['-i', str(A / 'amb_bubble.wav')]                      # 14
    fc = []
    for i, m in enumerate(man, 1):
        ms = int(NARR[i] * 1000)
        fc.append(f'[{i}:a]adelay={ms}|{ms}[n{i}]')
    fc.append(''.join(f'[n{k}]' for k in range(1, 13)) + 'amix=inputs=12:normalize=0[narr]')
    fc.append('[narr]asplit=2[narrA][narrB]')
    fc.append(f'[0:a]volume=0.62,afade=t=out:st={TOTAL - 2.5}:d=2.5[bgm0]')
    fc.append('[bgm0][narrB]sidechaincompress=threshold=0.028:ratio=7:attack=140:'
              'release=900:makeup=1[bgmD]')
    fc.append(f'[13:a]atrim=0:{TOTAL},volume=0.30,afade=t=out:st={TOTAL - 2}:d=2[rv]')
    b8 = STARTS[8]
    fc.append(f'[14:a]adelay={int((b8 - 0.6) * 1000)}|{int((b8 - 0.6) * 1000)},'
              f'atrim=0:{TOTAL - b8 + 0.6},volume=0.85[bub]')
    fc.append(f'[narrA][bgmD][rv][bub]amix=inputs=4:normalize=0[mix]')
    fc.append(f'[mix]loudnorm=I=-16:TP=-1.5:LRA=11,atrim=0:{TOTAL},apad=whole_dur={TOTAL}[aout]')
    script = W / 'audio.txt'
    script.write_text(';\n'.join(fc), encoding='utf-8')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-filter_complex_script', str(script),
         '-map', '[aout]', '-ar', '48000', '-c:a', 'aac', '-b:a', '224k',
         str(W / 'audio.m4a')])
    print('audio mix done')


def mux():
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(W / 'visual.mp4'),
         '-i', str(W / 'audio.m4a'),
         '-vf', f'fade=t=in:st=0:d=0.7,fade=t=out:st={TOTAL - 1.2}:d=1.2',
         '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-crf', '17',
         '-preset', 'slow', '-c:a', 'copy', '-movflags', '+faststart',
         str(OUT / '让水体重新呼吸_微纳米气泡黑臭水体治理实践_v1.mp4')])
    print('MUX DONE ->', OUT)


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print('schedule:', json.dumps(SCENES_DUR), 'total', TOTAL)
    if step in ('scene', 'all'):
        render_scenes()
    if step in ('concat', 'all'):
        concat()
    if step in ('overlay', 'all'):
        make_ass()
        overlay()
    if step in ('audio', 'all'):
        audio_mix()
        mux()


if __name__ == '__main__':
    main()
