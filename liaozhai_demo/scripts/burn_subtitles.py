"""Subtitle/typography burn for liaozhai_demo - PIL per-frame, 1920x1080.

Styles: narration (bottom, like the reference film's bold white-on-black),
title-card typography (gold main + subs + warning), end-card typography,
persistent AI corner label.
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
from ffmpeg_env import prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
MAX_TEXT_WIDTH = 1700

GOLD = (232, 196, 96, 255)
PAPER = (238, 232, 220, 255)
GREY = (178, 182, 192, 225)

STYLES = {
    'narr':       {'size': 58, 'color': (255, 255, 255, 255), 'stroke': (0, 0, 0, 255), 'sw': 3, 'y': 952},
    'title_main': {'size': 138, 'color': GOLD, 'stroke': (0, 0, 0, 255), 'sw': 5, 'y': 400},
    'title_sub':  {'size': 46, 'color': PAPER, 'stroke': (0, 0, 0, 200), 'sw': 2, 'y': 590},
    'title_sub2': {'size': 38, 'color': GREY, 'stroke': None, 'sw': 0, 'y': 680},
    'title_warn': {'size': 34, 'color': (210, 205, 195, 235), 'stroke': None, 'sw': 0, 'y': 950},
    'corner':     {'size': 27, 'color': (215, 215, 215, 185), 'stroke': (0, 0, 0, 140), 'sw': 2,
                   'y': 1032, 'align': 'left', 'x': 40},
    'end_main':   {'size': 88, 'color': PAPER, 'stroke': (0, 0, 0, 255), 'sw': 4, 'y': 430},
    'end_title':  {'size': 38, 'color': GREY, 'stroke': None, 'sw': 0, 'y': 580},
    'end_ai':     {'size': 40, 'color': (16, 22, 34, 255), 'stroke': None, 'sw': 0, 'y': 740,
                   'box': ((240, 243, 248, 235), 36, 18, 999)},
    'end_note':   {'size': 28, 'color': (150, 158, 172, 220), 'stroke': None, 'sw': 0, 'y': 920},
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
    box = cfg.get('box')
    pad_x = box[1] if box else 0
    pad_y = box[2] if box else 0

    total_h = line_h * len(lines) + 2 * pad_y
    y0 = cfg['y'] - pad_y if len(lines) == 1 else cfg['y'] - total_h // 2
    if box:
        widest = max(text_width(draw, ln, font) for ln in lines)
        bw = widest + 2 * pad_x
        bx = cfg.get('x', (vw - bw) // 2) if cfg.get('align') == 'left' else (vw - bw) // 2
        fill, _, _, radius = box[0], box[1], box[2], box[3]
        draw.rounded_rectangle([bx, y0, bx + bw, y0 + total_h], radius=radius, fill=fill)

    for li, text in enumerate(lines):
        w = text_width(draw, text, font)
        x = cfg.get('x', (vw - w) // 2) if cfg.get('align') == 'left' else (vw - w) // 2
        y = y0 + pad_y + li * line_h
        if cfg.get('sw'):
            sw = cfg['sw']
            for dx in range(-sw, sw + 1):
                for dy in range(-sw, sw + 1):
                    if dx * dx + dy * dy <= sw * sw:
                        draw.text((x + dx, y + dy), text, font=font, fill=cfg['stroke'])
        else:
            draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 130))
        draw.text((x, y), text, font=font, fill=cfg['color'])


def get_active(events, t):
    return [e for e in events if e['start'] <= t <= e['end']]


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    src = PROJECT / '07_edit/LZ_WITH_AUDIO.mp4'
    dst = PROJECT / '07_edit/LZ_WITH_SUBTITLES.mp4'
    TMP = Path('C:/Users/pc/AppData/Local/Temp') / f'lz_subs_{time.strftime("%Y%m%d_%H%M%S")}'

    if not src.exists():
        print(f'ERROR: {src} not found')
        sys.exit(1)

    info = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate', '-of', 'default=noprint_wrappers=1',
        str(src)]).decode()
    vw = int([l for l in info.split('\n') if l.startswith('width=')][0].split('=')[1])
    vh = int([l for l in info.split('\n') if l.startswith('height=')][0].split('=')[1])
    fr = [l for l in info.split('\n') if 'avg_frame_rate' in l][0].split('=')[1].strip().split('/')
    fps = float(fr[0]) / float(fr[1])
    total = tl['total_duration']
    frames_n = int(total * fps) + 1
    print(f'{vw}x{vh} @ {fps}fps, ~{frames_n} frames, {len(tl["subtitle_events"])} events')

    probe = Image.new('RGB', (vw, vh))
    pd = ImageDraw.Draw(probe)
    print('width pre-check:')
    all_ok = True
    for e in tl['subtitle_events']:
        lines = wrap_text(pd, e['text'], e['style'], vw)
        for ln in lines:
            w = text_width(pd, ln, get_font(STYLES[e['style']]['size']))
            ok = w + 2 * (STYLES[e['style']].get('box', ((0, 0, 0, 0), 0, 0, 0))[1] or 0) <= vw - 60
            all_ok &= ok
            if not ok:
                print(f'  [{w}px FAIL] {ln}')
    print(f'  all fit: {"YES" if all_ok else "NO"}')
    if not all_ok:
        sys.exit(2)

    TMP.mkdir(parents=True, exist_ok=True)
    print('extracting frames ...')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
                    '-vsync', '0', str(TMP / 'frame_%05d.png')], check=True)
    frames = sorted(TMP.glob('frame_*.png'))
    print(f'  {len(frames)} frames')

    events = tl['subtitle_events']
    print('burning ...')
    t0 = time.time()
    for i, fp in enumerate(frames):
        t = i / fps
        active = get_active(events, t)
        if active:
            img = Image.open(fp).convert('RGBA')
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for e in active:
                draw_event(draw, e, vw)
            Image.alpha_composite(img, overlay).convert('RGB').save(fp)
        if (i + 1) % 200 == 0:
            el = time.time() - t0
            print(f'  [{i+1}/{len(frames)}] {el:.0f}s ETA {el/(i+1)*(len(frames)-i-1):.0f}s')

    print('encoding (with head/tail fade) ...')
    fade_out_st = max(0.0, total - 1.2)
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', str(fps), '-i', str(TMP / 'frame_%05d.png'),
        '-i', str(src),
        '-map', '0:v', '-map', '1:a:0?',
        '-vf', f'fade=t=in:st=0:d=0.6,fade=t=out:st={fade_out_st:.3f}:d=1.2',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'copy', '-pix_fmt', 'yuv420p',
        '-t', str(total),
        str(dst)
    ], check=True)

    shutil.rmtree(TMP, ignore_errors=True)
    print(f'=== SUBTITLES BURNED ===\n  {dst} ({dst.stat().st_size/1024/1024:.1f}MB)')


if __name__ == '__main__':
    main()
