"""Subtitle/typography burn for third_lantern《第三盏灯》- PNG frame loop (PROVEN).

NOTE: a streamed rawvideo-pipe version of this stage was attempted (10x
faster) but produced torn/grayscale frames - the RGBA->RGB path in the pipe
corrupts the base picture. Reverted to the proven extract-PNG-burn-reencode
loop. Do not re-attempt streaming without debugging against a known-good
reference (see _ref_analysis prepost/burnfix experiments, 2026-09-25).
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import FFMPEG, prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/third_lantern')
MAX_TEXT_WIDTH = 1700

INK = (242, 236, 224, 255)          # 米白
GOLD = (226, 198, 132, 255)
MIST = (198, 206, 214, 235)

STYLES = {
    'narr':       {'size': 52, 'color': INK, 'stroke': (10, 12, 16, 235), 'sw': 3, 'y': 968},
    'rule_head':  {'size': 40, 'color': GOLD, 'stroke': (10, 12, 16, 220), 'sw': 2, 'y': 300},
    'rule_body':  {'size': 62, 'color': INK, 'stroke': (10, 12, 16, 235), 'sw': 4, 'y': 380},
    'title_main': {'size': 138, 'color': GOLD, 'stroke': (8, 10, 14, 255), 'sw': 5, 'y': 420},
    'title_sub':  {'size': 44, 'color': (226, 205, 160, 255), 'stroke': (8, 10, 14, 200),
                   'sw': 2, 'y': 610},
    'end_line1':  {'size': 62, 'color': INK, 'stroke': (8, 10, 14, 240), 'sw': 3, 'y': 400},
    'end_line2':  {'size': 62, 'color': INK, 'stroke': (8, 10, 14, 240), 'sw': 3, 'y': 545},
    'end_title':  {'size': 38, 'color': MIST, 'stroke': None, 'sw': 0, 'y': 620},
}

_FONT_CACHE = {}


def get_font(size):
    if size not in _FONT_CACHE:
        for path in ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/msyh.ttc',
                     'C:/Windows/Fonts/simhei.ttf'):
            if Path(path).exists():
                try:
                    _FONT_CACHE[size] = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
        else:
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def text_width(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def wrap_text(draw, text, style_name, vw):
    font = get_font(STYLES[style_name]['size'])
    if text_width(draw, text, font) <= MAX_TEXT_WIDTH:
        return [text]
    puncts = '，、！？…：;,!?'
    best = None
    for i, ch in enumerate(text):
        if ch in puncts and 0 < i + 1 < len(text):
            w = text_width(draw, text[:i + 1], font)
            if w <= MAX_TEXT_WIDTH and text_width(draw, text[i + 1:], font) <= MAX_TEXT_WIDTH:
                score = abs(w - vw * 0.42)
                if best is None or score < best[0]:
                    best = (score, i + 1)
    if best is None:
        best = (0, len(text) // 2)
    return [text[:best[1]].rstrip(), text[best[1]:].lstrip()]


def draw_event(draw, e, vw):
    cfg = STYLES[e['style']]
    font = get_font(cfg['size'])
    lines = wrap_text(draw, e['text'], e['style'], vw)
    line_h = int(cfg['size'] * 1.38)

    total_h = line_h * len(lines)
    y0 = cfg['y'] if len(lines) == 1 else cfg['y'] - total_h // 2

    for li, text in enumerate(lines):
        w = text_width(draw, text, font)
        x = cfg.get('x', (vw - w) // 2) if cfg.get('align') == 'left' else (vw - w) // 2
        y = y0 + li * line_h
        if cfg.get('sw'):
            sw = cfg['sw']
            for dx in range(-sw, sw + 1):
                for dy in range(-sw, sw + 1):
                    if dx * dx + dy * dy <= sw * sw:
                        draw.text((x + dx, y + dy), text, font=font, fill=cfg['stroke'])
        else:
            draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), text, font=font, fill=cfg['color'])


def scale_styles(vw, vh):
    f = vh / 1080.0
    for st in STYLES.values():
        st['size'] = max(8, round(st['size'] * f))
        st['y'] = round(st['y'] * f)
        if 'x' in st:
            st['x'] = round(st['x'] * f)
        if st.get('sw'):
            st['sw'] = max(1, round(st['sw'] * f))
    global MAX_TEXT_WIDTH
    MAX_TEXT_WIDTH = int(vw * 0.885)


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    src = PROJECT / '07_edit/TL_WITH_AUDIO.mp4'
    dst = PROJECT / '07_edit/TL_WITH_SUBTITLES.mp4'
    TMP = Path('C:/Users/pc/AppData/Local/Temp') / f'tl_subs_{time.strftime("%Y%m%d_%H%M%S")}'

    if not src.exists():
        print(f'ERROR: {src} not found')
        sys.exit(1)

    info = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate', '-of',
        'default=noprint_wrappers=1', str(src)]).decode()
    vw = int([l for l in info.split('\n') if l.startswith('width=')][0].split('=')[1])
    vh = int([l for l in info.split('\n') if l.startswith('height=')][0].split('=')[1])
    fr = [l for l in info.split('\n') if 'avg_frame_rate' in l][0].split('=')[1].strip().split('/')
    fps = float(fr[0]) / float(fr[1])
    total = tl['total_duration']
    scale_styles(vw, vh)
    est_frames = int(total * fps) + 1
    print(f'{vw}x{vh} @ {fps}fps, ~{est_frames} frames, {len(tl["subtitle_events"])} events')

    # width pre-check
    probe = Image.new('RGB', (vw, vh))
    pd = ImageDraw.Draw(probe)
    all_ok = True
    for e in tl['subtitle_events']:
        for ln in wrap_text(pd, e['text'], e['style'], vw):
            w = text_width(pd, ln, get_font(STYLES[e['style']]['size']))
            all_ok &= (w <= vw - 60)
    print(f'  width fit: {"YES" if all_ok else "NO"}')
    if not all_ok:
        sys.exit(2)

    TMP.mkdir(parents=True, exist_ok=True)
    print('extracting frames ...')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
                    '-vsync', '0', str(TMP / 'frame_%05d.png')], check=True)
    frames = sorted(TMP.glob('frame_*.png'))

    events = tl['subtitle_events']
    print('burning ...')
    t0 = time.time()
    for i, fp in enumerate(frames):
        t = i / fps
        active = [e for e in events if e['start'] <= t <= e['end']]
        if active:
            img = Image.open(fp).convert('RGBA')
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for e in active:
                draw_event(draw, e, vw)
            Image.alpha_composite(img, overlay).convert('RGB').save(fp)
        if (i + 1) % 400 == 0:
            el = time.time() - t0
            print(f'  [{i+1}/{len(frames)}] {el:.0f}s ETA {el/(i+1)*(len(frames)-i-1):.0f}s')

    print('encoding (with head/tail fade) ...')
    fade_out_st = max(0.0, total - 1.5)
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', str(fps), '-i', str(TMP / 'frame_%05d.png'),
        '-i', str(src),
        '-map', '0:v', '-map', '1:a:0?',
        '-vf', f'fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_st:.3f}:d=1.5',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
        '-c:a', 'copy', '-pix_fmt', 'yuv420p',
        '-t', str(total),
        str(dst)
    ], check=True)

    shutil.rmtree(TMP, ignore_errors=True)
    print(f'=== SUBTITLES BURNED ===\n  {dst} ({dst.stat().st_size/1024/1024:.1f}MB)')


if __name__ == '__main__':
    main()
