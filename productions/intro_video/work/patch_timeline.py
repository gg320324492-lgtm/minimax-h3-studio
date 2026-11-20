"""重排 model-intro 时间轴：场景之间留固定间隙，用闪白做过渡。

交叉叠化（两场同时在场）试过 12 帧和 8 帧，两场的文字都会在半透明状态下
交叠成重影，看着像渲染错误。改成：旧场淡出 → 6 帧空档（由一记闪白盖住）
→ 新场淡入。两场文字从此不会同时出现在同一帧上。

音频文件本身不变，只改它们在时间轴上的落点与字幕的出入点。
"""
import json
from pathlib import Path

FPS = 24
GAP = 6           # 场景之间的空档帧数（同时用作淡入/淡出帧数）
HEAD = 0.25        # 语音开始前的呼吸
TAIL = 0.55        # 语音结束后的留白（字幕淡出用掉 10 帧）

TARGET = Path(r'E:/Minimax-H3/studio/src/templates/model-intro/timeline.json')

tl = json.loads(TARGET.read_text(encoding='utf-8'))
scenes = tl['scenes']

for scene in scenes:
    scene['head'] = HEAD
    scene['tail'] = TAIL
    scene['duration'] = round(HEAD + scene['spoken'] + TAIL, 3)

for index, scene in enumerate(scenes):
    if index == 0:
        scene['start'] = 0.0
    else:
        prev = scenes[index - 1]
        scene['start'] = round(prev['start'] + prev['duration'] + GAP / FPS, 3)
    audio_in = round(HEAD * FPS)
    spoken_frames = round(scene['spoken'] * FPS)
    scene['audioInFrame'] = audio_in
    scene['audioEndFrame'] = audio_in + spoken_frames
    scene['captionInFrame'] = audio_in + 2
    # 字幕末 8 帧淡出，起点落在语音结束之后 2 帧
    scene['captionOutFrame'] = scene['audioEndFrame'] + 10

tl['fps'] = FPS
tl['overlapFrames'] = GAP
tl['headSeconds'] = HEAD
tl['tailSeconds'] = TAIL
tl['totalSeconds'] = round(scenes[-1]['start'] + scenes[-1]['duration'], 3)

TARGET.write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'gap={GAP}f  head={HEAD}s  tail={TAIL}s  total={tl["totalSeconds"]}s')
for scene in scenes:
    print(
        f'  {scene["id"]:<9} start={scene["start"]:6.2f}  dur={scene["duration"]:5.2f}  '
        f'audio_in={scene["audioInFrame"]:>3}  audio_end={scene["audioEndFrame"]:>3}  '
        f'caption={scene["captionInFrame"]}→{scene["captionOutFrame"]}'
    )
