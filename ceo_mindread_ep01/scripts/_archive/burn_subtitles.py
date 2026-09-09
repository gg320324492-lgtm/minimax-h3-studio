"""Generate ASS subtitle file and burn into final video for CEO Mindread EP01.

ASS format supports:
- Position
- Font size
- Color
- Outline/stroke
- Multiple styles

Style requirements:
- 56-68px font size
- White text
- Black stroke 2-4px
- Subtle shadow
- 内心独白 (inner voice): 浅黄色 with 【心声】prefix
"""
import subprocess
import sys
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3/ceo_mindread_ep01')

# Timeline: (start_s, end_s, text, type)
# type: 'normal', 'inner' (心声), 'opening' (开屏文字)
subtitles = [
    # First 3 seconds: opening subtitle (强制首屏)
    (0.0, 1.5, '我突然听见了', 'opening'),
    (1.5, 2.8, '实习生的心声', 'opening'),
    (2.8, 4.4, '她说：', 'opening'),
    (2.8, 4.4, '我还有7秒就会死', 'opening_special'),  # 7秒 放大

    # S02: countdown
    (5.0, 6.5, '【心声】六……五……四……', 'inner'),

    # S03: 三…二…
    (9.8, 11.5, '【心声】三……二……', 'inner'),

    # S04
    (14.0, 17.5, '【心声】他怎么没死？', 'inner'),
    (15.0, 17.5, '前七次明明都死在这里……', 'inner'),

    # S05: coffee
    (18.2, 20.5, '顾总，您的您的。', 'normal'),  # 您的咖啡
    (19.5, 22.0, '【心声】别喝啊！里面有花生酱', 'inner'),
    (20.5, 22.0, '你不是严重过敏吗？', 'inner'),

    # S06
    (22.5, 23.0, '林小雨。', 'normal'),
    (23.5, 24.0, '顾……顾总？', 'normal'),
    (24.5, 25.0, '你到底是谁？', 'normal'),
    (25.0, 25.5, '实习生啊……', 'normal'),
    (25.5, 27.0, '【心声】第八次循环', 'inner_special'),
    (25.5, 27.0, '他第一次活到了09:17', 'inner_special'),

    # S08
    (29.0, 30.5, '【心声】第八次循环……又开始了。', 'inner'),
    (30.5, 32.5, '【心声】但是这一次……', 'inner'),
    (31.0, 32.5, '要死的人，好像是我。', 'inner_special'),

    # S09 ending
    (33.5, 35.0, '下一次死亡倒计时', 'ending'),
    (33.5, 35.0, '09:23', 'ending_special'),
]


def create_ass_file():
    """Create ASS subtitle file."""
    ass_path = PROJECT / '06_subtitles/EP01.ass'

    # ASS header with styles
    ass_content = '''[Script Info]
Title: CEO Mindread EP01
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
# Normal subtitle style
Style: Default,Microsoft YaHei,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,200,1
# Inner voice style (yellow with bracket)
Style: Inner,Microsoft YaHei,56,&H0000D4FF,&H0000D4FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,180,1
# Opening subtitle (larger, top of screen)
Style: Opening,Microsoft YaHei,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,8,80,80,200,1
# Special emphasis (red)
Style: Special,Microsoft YaHei,80,&H000000FF,&H000000FF,&H00FFFFFF,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,80,80,250,1
# Inner voice special emphasis
Style: InnerSpecial,Microsoft YaHei,72,&H0000D4FF,&H0000D4FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,2,80,80,200,1
# Ending
Style: Ending,Microsoft YaHei,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,5,80,80,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''

    # Convert timeline to ASS events
    def s_to_ass_time(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        cs = int((s % 1) * 100)
        return f'{h:01d}:{m:02d}:{sec:02d}.{cs:02d}'

    for start_s, end_s, text, stype in subtitles:
        # Map type to style
        style_map = {
            'normal': 'Default',
            'inner': 'Inner',
            'opening': 'Opening',
            'opening_special': 'Special',
            'inner_special': 'InnerSpecial',
            'ending': 'Ending',
            'ending_special': 'Special',
        }
        style = style_map.get(stype, 'Default')
        start_t = s_to_ass_time(start_s)
        end_t = s_to_ass_time(end_s)
        # Escape text
        text_esc = text.replace('\n', '\\N')
        ass_content += f'Dialogue: 0,{start_t},{end_t},{style},,0,0,0,,{text_esc}\n'

    ass_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(ass_content, encoding='utf-8')
    print(f'Wrote: {ass_path}')
    return ass_path


def burn_subtitles(input_video, output_video, ass_file):
    """Burn subtitles using ffmpeg ass filter."""
    # Use libass filter
    ass_escaped = str(ass_file).replace('\\', '/').replace(':', '\\:')
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(input_video),
        '-vf', f"ass='{ass_escaped}'",
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'copy',
        '-pix_fmt', 'yuv420p',
        str(output_video)
    ]
    print(f'Burning subtitles...')
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr.decode()[:1500])
        return False
    return True


if __name__ == '__main__':
    ass_path = create_ass_file()
    input_video = PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'
    output_video = PROJECT / '07_edit/EP01_WITH_SUBTITLES.mp4'
    if burn_subtitles(input_video, output_video, ass_path):
        print(f'\n=== SUBTITLES BURNED ===')
        print(f'  {output_video}')
        print(f'  size: {output_video.stat().st_size/1024/1024:.1f}MB')