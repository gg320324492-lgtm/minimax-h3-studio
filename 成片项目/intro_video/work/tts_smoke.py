import os
os.environ['HF_HUB_CACHE'] = 'E:/Minimax-H3/third_party/ComfyUI/models/tts'
os.environ['HF_HUB_OFFLINE'] = '1'
from kokoro import KPipeline
import soundfile as sf

pipeline = KPipeline(lang_code='z', model=True, repo_id='hexgrad/Kokoro-82M')
text = '你好。我是一个语言模型，此刻就在这台机器上运行。'
chunks = []
for gs, ps, audio in pipeline(text, voice='zm_yunyang', speed=1.0):
    if audio is not None and len(audio):
        chunks.append(audio)
    break
audio = chunks[0] if chunks else None
print('audio len', None if audio is None else len(audio))
if audio is not None:
    sf.write('smoke.wav', audio, 24000)
    print('duration_s', len(audio)/24000)
