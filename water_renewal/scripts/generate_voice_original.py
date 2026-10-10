import json,sys,subprocess,os
from pathlib import Path
import numpy as np,soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG,FFPROBE
os.environ['HF_HUB_CACHE']='E:/ComfyUI/models/tts'
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'00_project/editorial.json').read_text(encoding='utf-8'))
OUT=ROOT/'05_audio/narration';OUT.mkdir(parents=True,exist_ok=True)
def duration(p):return float(subprocess.check_output([FFPROBE,'-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
from kokoro import KPipeline
pipeline=KPipeline(lang_code='z',model=True,repo_id='hexgrad/Kokoro-82M')
manifest=[]
previous={x['id']:x for x in json.loads((ROOT/'00_project/voice_manifest.json').read_text(encoding='utf-8'))} if (ROOT/'00_project/voice_manifest.json').exists() else {}
for line in CFG['narration']:
 if sys.argv[1:] and line['id'] not in sys.argv[1:]:
  manifest.append(previous[line['id']]);continue
 raw=OUT/(line['id']+'_original_voice_raw.wav');final=OUT/(line['id']+'.wav')
 text_cache=raw.with_suffix('.txt')
 if not raw.exists() or (text_cache.exists() and text_cache.read_text(encoding='utf-8')!=line['text']) or line['id'] in sys.argv[1:]:
  chunks=[a for gs,ps,a in pipeline(line['text'],voice='zm_yunyang',speed=.87) if a is not None and len(a)]
  if not chunks:raise RuntimeError(line['id'])
  sf.write(raw,np.concatenate(chunks),24000)
 text_cache.write_text(line['text'],encoding='utf-8')
 trim=OUT/(line['id']+'_original_voice_trim.wav')
 subprocess.run([FFMPEG,'-v','error','-y','-i',str(raw),'-af','silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,areverse',str(trim)],check=True)
 d=duration(trim);speed=max(.85,d/line['slot'])
 subprocess.run([FFMPEG,'-v','error','-y','-i',str(trim),'-af',f'atempo={speed:.5f},highpass=f=75,loudnorm=I=-17:TP=-2:LRA=8','-ar','48000','-ac','1',str(final)],check=True)
 manifest.append({**line,'file':str(final),'duration':duration(final),'speed':speed,'voice':'Kokoro-82M / zm_yunyang (same as first film)'})
 print(line['id'],'original voice',duration(final),flush=True)
(ROOT/'00_project/voice_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
