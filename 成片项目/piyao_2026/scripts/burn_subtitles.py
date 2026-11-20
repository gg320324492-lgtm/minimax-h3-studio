"""Subtitle burn for piyao_2026 - timeline-driven, 1920x1080 landscape.

Style families:
  narr/hook/slogan      bottom narration lines
  msg                   chat-bubble box (the fake viral message)
  step                  big blue step cards (查时间/查地点/查来源)
  card                  dark box reinforcement cards
  title                 opening film title
  corner                persistent AI-label disclaimer, bottom-left, small
  end_*                 end-card typography (slogan/theme/title/AI pill/note)

Any line wider than MAX_TEXT_WIDTH is wrapped at punctuation (pre-checked).
First/last second of the film gets a fade on the final encode.
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

PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
MAX_TEXT_WIDTH = 1700

# box: (fill rgba, pad_x, pad_y, radius)  -> rounded rect behind the text
STYLES = {
    'narr':       {'size': 54, 'color': (255, 255, 255, 255), 'stroke': (0, 0, 0, 255), 'sw': 3, 'y': 962},
    'hook':       {'size': 64, 'color': (255, 235, 120, 255), 'stroke': (0, 0, 0, 255), 'sw': 3, 'y': 900},
    'slogan':     {'size': 68, 'color': (255, 210, 77, 255),  'stroke': (0, 0, 0, 255), 'sw': 4, 'y': 890},
    'msg':        {'size': 46, 'color': (255, 255, 255, 255), 'stroke': None, 'sw': 0, 'y': 150,
                   'box': ((18, 22, 32, 215), 46, 26, 22)},
    'step':       {'size': 76, 'color': (255, 255, 255, 255), 'stroke': None, 'sw': 0, 'y': 170,
                   'box': ((24, 58, 118, 200), 60, 30, 26)},
    'card':       {'size': 58, 'color': (255, 235, 120, 255), 'stroke': None, 'sw': 0, 'y': 820,
                   'box': ((10, 12, 18, 200), 50, 26, 20)},
    'title':      {'size': 44, 'color': (255, 255, 255, 235), 'stroke': (0, 0, 0, 200), 'sw': 2, 'y': 96},
    'corner':     {'size': 27, 'color': (215, 215, 215, 185), 'stroke': (0, 0, 0, 140), 'sw': 2,
                   'y': 1032, 'align': 'left', 'x': 40},
    'end_slogan': {'size': 96, 'color': (255, 255, 255, 255), 'stroke': (0, 0, 0, 255), 'sw': 4, 'y': 380},
    'end_theme':  {'size': 60, 'color': (255, 210, 77, 255),  'stroke': (0, 0, 0, 220), 'sw': 3, 'y': 548},
    'end_title':  {'size': 34, 'color': (205, 214, 228, 255), 'stroke': None, 'sw': 0, 'y': 688},
    'end_ai':     {'size': 40, 'color': (16, 22, 34, 255),    'stroke': None, 'sw': 0, 'y': 790,
                   'box': ((240, 243, 248, 235), 36, 18, 999)},
    'end_note':   {'size': 28, 'color': (150, 160, 176, 220), 'stroke': None, 'sw': 0, 'y': 920},
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


def draw_box(draw, x0, y0, x1, y1, box_cfg):
    fill, _, _, radius = box_cfg
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


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
        draw_box(draw, bx, y0, bx + bw, y0 + total_h, box)

    for li, text in enumerate(lines):
        w = text_width(draw, text, font)
        x = cfg.get('x', (vw - w) // 2) if cfg.get('align') == 'left' else (vw - w) // 2
        y = y0 + pad_y + li * line_h
        off = 3
        draw.text((x + off, y + off), text, font=font, fill=(0, 0, 0, 160))
        if cfg.get('sw'):
            sw = cfg['sw']
            for dx in range(-sw, sw + 1):
                for dy in range(-sw, sw + 1):
                    if dx * dx + dy * dy <= sw * sw:
                        draw.text((x + dx, y + dy), text, font=font, fill=cfg['stroke'])
        draw.text((x, y), text, font=font, fill=cfg['color'])


def get_active(events, t):
    return [e for e in events if e['start'] <= t <= e['end']]


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    src = PROJECT / '07_edit/PIYAO_WITH_AUDIO.mp4'
    dst = PROJECT / '07_edit/PIYAO_WITH_SUBTITLES.mp4'
    TMP = Path('C:/Users/pc/AppData/Local/Temp') / f'piyao_subs_{time.strftime("%Y%m%d_%H%M%S")}'

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
