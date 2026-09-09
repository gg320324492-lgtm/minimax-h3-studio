"""Subtitle burn v2 - timeline-driven + automatic line wrapping.

Reads 00_project/timeline.json (built by build_timeline.py).
Wraps any subtitle wider than MAX_TEXT_WIDTH at punctuation into <= 2 lines.
"""
import json
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
MAX_TEXT_WIDTH = 1000  # px, frame is 1080 wide; keep margin

STYLES = {
    'normal':        {'font_size': 56, 'color': (255, 255, 255),   'stroke': (0, 0, 0),       'sw': 3, 'y': 1620},
    'inner':         {'font_size': 52, 'color': (255, 235, 100),   'stroke': (0, 0, 0),       'sw': 3, 'y': 1620},
    'opening':       {'font_size': 72, 'color': (255, 255, 255),   'stroke': (0, 0, 0),       'sw': 4, 'y': 400},
    'special':       {'font_size': 76, 'color': (255, 50, 50),     'stroke': (255, 255, 255), 'sw': 4, 'y': 1620},
    'inner_special': {'font_size': 64, 'color': (255, 235, 100),   'stroke': (0, 0, 0),       'sw': 4, 'y': 1620},
    'ending':        {'font_size': 72, 'color': (255, 255, 255),   'stroke': (0, 0, 0),       'sw': 4, 'y': 1560},
}

_FONT_CACHE = {}


def get_font(size):
    if size not in _FONT_CACHE:
        for path in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
                     'C:/Windows/Fonts/NotoSansSC-VF.ttf'):
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
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_text(draw, text, style_name, video_w):
    """Split into <=2 lines at the punctuation nearest the center if too wide."""
    cfg = STYLES[style_name]
    font = get_font(cfg['font_size'])
    if text_width(draw, text, font) <= MAX_TEXT_WIDTH:
        return [text]

    # find candidate split points (after punctuation), pick closest to middle width
    puncts = '，、！？…：;,!?'
    best = None
    for i, ch in enumerate(text):
        if ch in puncts and 0 < i + 1 < len(text):
            w = text_width(draw, text[:i + 1], font)
            if w <= MAX_TEXT_WIDTH and text_width(draw, text[i + 1:], font) <= MAX_TEXT_WIDTH:
                score = abs(w - video_w * 0.42)
                if best is None or score < best[0]:
                    best = (score, i + 1)
    if best is None:
        # hard split near middle by characters
        mid = len(text) // 2
        best = (0, mid)
    split = best[1]
    return [text[:split].rstrip(), text[split:].lstrip()]


def draw_subtitle(draw, lines, style_name, video_w):
    cfg = STYLES[style_name]
    font = get_font(cfg['font_size'])
    line_h = int(cfg['font_size'] * 1.35)
    total_h = line_h * len(lines)
    y0 = cfg['y'] if len(lines) == 1 else cfg['y'] - total_h // 2 + line_h // 2

    for li, text in enumerate(lines):
        w = text_width(draw, text, font)
        x = (video_w - w) // 2
        y = y0 + li * line_h
        # shadow
        off = 4
        draw.text((x + off, y + off), text, font=font, fill=(0, 0, 0, 190))
        # stroke
        sw = cfg['sw']
        for dx in range(-sw, sw + 1):
            for dy in range(-sw, sw + 1):
                if dx * dx + dy * dy <= sw * sw:
                    draw.text((x + dx, y + dy), text, font=font, fill=cfg['stroke'])
        # main
        draw.text((x, y), text, font=font, fill=cfg['color'])


def get_active(events, t):
    return [e for e in events if e['start'] <= t <= e['end']]


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    input_video = PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'
    output_video = PROJECT / '07_edit/EP01_WITH_SUBTITLES.mp4'
    TMP = Path('C:/Users/pc/AppData/Local/Temp/sub_burn_v2')

    if not input_video.exists():
        print(f'ERROR: {input_video} not found')
        return

    info = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate', '-of', 'default=noprint_wrappers=1',
        str(input_video)
    ]).decode()
    vw = int([l for l in info.split('\n') if l.startswith('width=')][0].split('=')[1])
    vh = int([l for l in info.split('\n') if l.startswith('height=')][0].split('=')[1])
    fps_parts = [l for l in info.split('\n') if 'avg_frame_rate' in l][0].split('=')[1].strip().split('/')
    fps = float(fps_parts[0]) / float(fps_parts[1])
    total = tl['total_duration']
    total_frames = int(total * fps) + 1
    print(f'{vw}x{vh} @ {fps}fps, ~{total_frames} frames, {len(tl["subtitle_events"])} subtitle events')

    # Pre-check subtitle widths (fail fast, part of QA)
    probe = Image.new('RGB', (vw, vh))
    probe_draw = ImageDraw.Draw(probe)
    print('\nSubtitle width pre-check:')
    all_ok = True
    for e in tl['subtitle_events']:
        lines = wrap_text(probe_draw, e['text'], e['style'], vw)
        for line in lines:
            w = text_width(probe_draw, line, get_font(STYLES[e['style']]['font_size']))
            ok = w <= MAX_TEXT_WIDTH
            all_ok &= ok
            if not ok or len(lines) > 1:
                print(f'  {w}px [{"OK" if ok else "FAIL"}] {" | ".join(lines)}')
    print(f'  all within {MAX_TEXT_WIDTH}px: {"YES" if all_ok else "NO"}')
    if not all_ok:
        print('ERROR: subtitle overflow remains - fix wrap logic')
        return

    TMP.mkdir(parents=True, exist_ok=True)
    for f in TMP.glob('*.png'):
        f.unlink()

    print('\nExtracting frames...')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(input_video),
                    '-vsync', '0', str(TMP / 'frame_%05d.png')], check=True)
    frames = sorted(TMP.glob('frame_*.png'))
    print(f'  {len(frames)} frames')

    # Group events by frame index for speed
    events = tl['subtitle_events']
    print('\nBurning subtitles...')
    t0 = time.time()
    for i, fp in enumerate(frames):
        t = i / fps
        active = get_active(events, t)
        if active:
            img = Image.open(fp).convert('RGBA')
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for e in active:
                lines = wrap_text(draw, e['text'], e['style'], vw)
                draw_subtitle(draw, lines, e['style'], vw)
            Image.alpha_composite(img, overlay).convert('RGB').save(fp)
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            print(f'  [{i+1}/{len(frames)}] {el:.0f}s ETA {el/(i+1)*(len(frames)-i-1):.0f}s')
    print(f'  done in {time.time()-t0:.1f}s')

    print('\nRe-encoding with audio...')
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', str(fps), '-i', str(TMP / 'frame_%05d.png'),
        '-i', str(input_video),
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'copy', '-pix_fmt', 'yuv420p',
        '-t', str(total),
        str(output_video)
    ], check=True)
    print(f'\n=== SUBTITLES BURNED ===\n  {output_video} ({output_video.stat().st_size/1024/1024:.1f}MB)')


if __name__ == '__main__':
    main()
