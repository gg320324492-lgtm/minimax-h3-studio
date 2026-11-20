"""Generate the narration track for the model-intro video with local Kokoro-82M.

Reads narration.json (single source of truth for lines), writes one m4a per line
into the Remotion public folder, and emits timeline.json with the real measured
duration of every clip so the composition timeline is driven by the voice.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r'E:\Minimax-H3')
sys.path.insert(0, r'E:\Minimax-H3\scripts')
from ffmpeg_env import prepend_to_path  # noqa: E402

prepend_to_path()

os.environ['HF_HUB_CACHE'] = 'E:/Minimax-H3/third_party/ComfyUI/models/tts'
os.environ['HF_HUB_OFFLINE'] = '1'

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from kokoro import KPipeline  # noqa: E402

ROOT = Path(r'E:/Minimax-H3/productions/intro_video')
STUDIO = Path(r'E:/Minimax-H3/studio')
AUDIO_OUT = STUDIO / 'public' / 'audio' / 'intro'
TIMELINE_OUT = STUDIO / 'src' / 'templates' / 'model-intro' / 'timeline.json'

# 场景首尾各留一点呼吸，最后一段单独留更长的收尾余量。
LEAD_IN = 0.30
TAIL = 0.45


def main() -> None:
    spec = json.loads((ROOT / 'narration.json').read_text(encoding='utf-8'))
    AUDIO_OUT.mkdir(parents=True, exist_ok=True)
    TIMELINE_OUT.parent.mkdir(parents=True, exist_ok=True)

    pipeline = KPipeline(lang_code='z', model=True, repo_id='hexgrad/Kokoro-82M')

    scenes = []
    cursor = 0.0
    for index, scene in enumerate(spec['scenes']):
        text = scene['line']
        audio = None
        for _gs, _ps, chunk in pipeline(text, voice=spec['voice'], speed=spec['speed']):
            if chunk is not None and len(chunk):
                audio = chunk
            break
        if audio is None:
            raise RuntimeError(f'Kokoro produced no audio for scene {scene["id"]}')

        wav = ROOT / 'work' / f'{scene["id"]}.wav'
        m4a = AUDIO_OUT / f'{scene["id"]}.m4a'
        sf.write(str(wav), np.asarray(audio, dtype='float32'), 24000)
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav),
             '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(m4a)],
            check=True,
        )
        wav.unlink(missing_ok=True)

        spoken = len(audio) / 24000
        # 场景从上一句结束后进入，首帧留 LEAD_IN 呼吸。
        start = cursor + (LEAD_IN if index > 0 else 0.0)
        duration = spoken + (TAIL if index == len(spec['scenes']) - 1 else 0.45)
        scenes.append({
            'id': scene['id'],
            'line': text,
            'caption': scene['caption'],
            'audio': f'audio/intro/{scene["id"]}.m4a',
            'start': round(start, 3),
            'duration': round(duration, 3),
            'spoken': round(spoken, 3),
        })
        cursor = start + duration
        print(f'  {scene["id"]:<9} spoken={spoken:5.2f}s  scene={duration:5.2f}s  start={start:6.2f}s')

    total = cursor
    timeline = {
        'title': spec['title'],
        'fps': 24,
        'width': 1920,
        'height': 1080,
        'totalSeconds': round(total, 3),
        'scenes': scenes,
    }
    TIMELINE_OUT.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\ntotal {total:.2f}s -> {TIMELINE_OUT}')


if __name__ == '__main__':
    main()
