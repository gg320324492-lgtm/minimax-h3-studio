"""Burn subtitles onto video using PIL (Python Imaging Library).

Since ffmpeg 4.2.11 doesn't have ass/drawtext filters,
we use PIL to draw subtitles frame-by-frame, then re-encode.

This is slower but produces quality output.
"""
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(r'E:/Minimax-H3/ceo_mindread_ep01')

# Subtitle timeline: (start_s, end_s, text, style)
# styles: 'normal', 'inner' (yellow), 'special' (red/larger)
subtitles = [
    # First 3 seconds: opening subtitle
    (0.0, 1.5, '我突然听见了', 'opening'),
    (1.5, 2.8, '实习生的心声', 'opening'),
    (2.8, 4.4, '她说：我还有7秒就会死', 'special'),

    # S02: countdown
    (5.0, 6.5, '【心声】六……五……四……', 'inner'),

    # S03
    (9.8, 11.5, '【心声】三……二……', 'inner'),

    # S04
    (14.0, 17.5, '【心声】他怎么没死？前七次明明都死在这里……', 'inner'),

    # S05
    (18.2, 20.5, '顾总，您的咖啡。', 'normal'),
    (19.5, 22.0, '【心声】别喝啊！里面有花生酱，你不是严重过敏吗？', 'inner'),

    # S06
    (22.5, 23.0, '林小雨。', 'normal'),
    (23.5, 24.0, '顾……顾总？', 'normal'),
    (24.5, 25.0, '你到底是谁？', 'normal'),
    (25.0, 25.5, '实习生啊……', 'normal'),
    (25.5, 27.0, '【心声】第八次循环，他第一次活到了09:17', 'inner_special'),

    # S08
    (29.0, 30.5, '【心声】第八次循环……又开始了。', 'inner'),
    (30.5, 32.5, '【心声】但是这一次……要死的人，好像是我。', 'inner_special'),

    # S09 ending
    (33.5, 35.5, '下一次死亡倒计时  09:23', 'special'),
]

# Style configurations
STYLES = {
    'normal': {
        'font_size': 56,
        'color': (255, 255, 255),
        'stroke_color': (0, 0, 0),
        'stroke_width': 3,
        'shadow': True,
        'y_position': 1620,  # Bottom safe area
        'alpha': 255,
    },
    'inner': {
        'font_size': 52,
        'color': (255, 235, 100),  # Yellow
        'stroke_color': (0, 0, 0),
        'stroke_width': 3,
        'shadow': True,
        'y_position': 1620,
        'alpha': 255,
    },
    'opening': {
        'font_size': 72,
        'color': (255, 255, 255),
        'stroke_color': (0, 0, 0),
        'stroke_width': 4,
        'shadow': True,
        'y_position': 400,  # Top area for opening
        'alpha': 255,
    },
    'special': {
        'font_size': 76,
        'color': (255, 50, 50),  # Red
        'stroke_color': (255, 255, 255),
        'stroke_width': 4,
        'shadow': True,
        'y_position': 1620,
        'alpha': 255,
    },
    'inner_special': {
        'font_size': 64,
        'color': (255, 235, 100),
        'stroke_color': (0, 0, 0),
        'stroke_width': 4,
        'shadow': True,
        'y_position': 1620,
        'alpha': 255,
    },
}


def get_font(size):
    """Get Chinese font."""
    # Try msyh.ttc first (Microsoft YaHei)
    for path in [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/NotoSansSC-VF.ttf',
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Fallback to default
    return ImageFont.load_default()


def draw_subtitle(draw, text, style_name, video_w, video_h):
    """Draw subtitle on the image."""
    cfg = STYLES[style_name]
    font = get_font(cfg['font_size'])

    # Use textbbox for accurate sizing
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Center horizontally
    x = (video_w - text_w) // 2
    y = cfg['y_position']

    # Draw shadow first
    if cfg['shadow']:
        shadow_offset = 4
        for dx in range(-cfg['stroke_width'], cfg['stroke_width'] + 1):
            for dy in range(-cfg['stroke_width'], cfg['stroke_width'] + 1):
                draw.text((x + dx + shadow_offset, y + dy + shadow_offset),
                          text, font=font, fill=(0, 0, 0, 200))

    # Draw stroke
    stroke_w = cfg['stroke_width']
    for dx in range(-stroke_w, stroke_w + 1):
        for dy in range(-stroke_w, stroke_w + 1):
            if dx*dx + dy*dy <= stroke_w*stroke_w:
                draw.text((x + dx, y + dy), text, font=font, fill=cfg['stroke_color'])

    # Draw main text
    draw.text((x, y), text, font=font, fill=cfg['color'])


def get_active_subtitles(t):
    """Get list of (text, style) for time t."""
    active = []
    for start, end, text, style in subtitles:
        if start <= t <= end:
            active.append((text, style))
    return active


def main():
    input_video = PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'
    output_video = PROJECT / '07_edit/EP01_WITH_SUBTITLES.mp4'
    TMP = Path('C:/Users/pc/AppData/Local/Temp/sub_burn')

    if not input_video.exists():
        print(f'ERROR: {input_video} not found')
        return

    # Get video info
    info = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_frames',
        '-of', 'default=noprint_wrappers=1',
        str(input_video)
    ]).decode()
    print('Video info:')
    print(info)

    # Parse FPS
    fps_line = [l for l in info.split('\n') if 'avg_frame_rate' in l][0]
    fps_parts = fps_line.split('=')[1].split('/')
    fps = float(fps_parts[0]) / float(fps_parts[1])

    # Parse dimensions
    w_line = [l for l in info.split('\n') if l.startswith('width=')][0]
    h_line = [l for l in info.split('\n') if l.startswith('height=')][0]
    vw = int(w_line.split('=')[1])
    vh = int(h_line.split('=')[1])

    # Parse total frames
    nf_line = [l for l in info.split('\n') if 'nb_frames' in l][0]
    total_frames = int(nf_line.split('=')[1])

    print(f'\n{vw}x{vh} @ {fps}fps, {total_frames} frames')

    # Setup temp dir
    TMP.mkdir(parents=True, exist_ok=True)
    for f in TMP.glob('*'):
        f.unlink()

    # Extract frames
    print('\nExtracting frames...')
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(input_video),
        '-vsync', '0',
        str(TMP / 'frame_%05d.png')
    ], check=True)

    frames = sorted(TMP.glob('frame_*.png'))
    print(f'  {len(frames)} frames extracted')

    # Burn subtitles onto each frame
    print('\nBurning subtitles...')
    t0 = time.time()
    for i, fp in enumerate(frames):
        # Calculate time
        t = i / fps

        # Open image
        img = Image.open(fp).convert('RGBA')
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw all active subtitles
        for text, style in get_active_subtitles(t):
            draw_subtitle(draw, text, style, vw, vh)

        # Composite
        combined = Image.alpha_composite(img, overlay).convert('RGB')
        combined.save(fp, quality=95)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (len(frames) - i - 1)
            print(f'  [{i+1}/{len(frames)}] {elapsed:.0f}s ETA {eta:.0f}s')

    print(f'  done in {time.time() - t0:.1f}s')

    # Re-encode with audio
    print('\nRe-encoding with audio...')
    audio_input = str(input_video)
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-framerate', str(fps),
        '-i', str(TMP / 'frame_%05d.png'),
        '-i', audio_input,
        '-map', '0:v',
        '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'copy',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        str(output_video)
    ]
    subprocess.run(cmd, check=True)
    print(f'\n=== SUBTITLES BURNED ===')
    print(f'  {output_video}')
    print(f'  size: {output_video.stat().st_size/1024/1024:.1f}MB')


if __name__ == '__main__':
    main()