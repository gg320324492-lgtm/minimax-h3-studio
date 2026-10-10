import json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG
from faster_whisper import WhisperModel
out=Path(__file__).resolve().parents[1]/'01_reference'
src=next(Path(r'C:\Users\pc\Desktop\设计短片\黑臭水体治理宣传视频').glob('成片*.mp4'))
subprocess.run([FFMPEG,'-v','error','-y','-i',str(src),'-vn','-ar','16000','-ac','1',str(out/'original_audio.wav')],check=True)
modelpath=next(Path(r'C:\Users\pc\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots').iterdir())
model=WhisperModel(str(modelpath),device='cpu',compute_type='int8')
segments,info=model.transcribe(str(out/'original_audio.wav'),language='zh',vad_filter=True,beam_size=5)
rows=[{'start':s.start,'end':s.end,'text':s.text} for s in segments]
(out/'original_transcript.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=True))
