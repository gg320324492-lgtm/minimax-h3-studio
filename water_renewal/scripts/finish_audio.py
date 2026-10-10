import json,sys,subprocess,re,difflib,hashlib
from pathlib import Path
import numpy as np,soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'00_project/editorial.json').read_text(encoding='utf-8'))
OUT=ROOT/'05_audio'
SR=48000;N=int(CFG['duration']*SR)
def load(p):
 x,sr=sf.read(p,dtype='float32',always_2d=True)
 if sr!=SR:x=resample_poly(x,SR,sr,axis=0)
 if x.shape[1]==1:x=np.repeat(x,2,axis=1)
 return x
def norm(x,db):return x*(10**(db/20)/max(1e-7,np.sqrt(np.mean(x*x))))
def fade(x,a=1,b=1):
 x=x.copy();na=min(len(x),int(a*SR));nb=min(len(x),int(b*SR))
 x[:na]*=np.linspace(0,1,na)[:,None];x[-nb:]*=np.linspace(1,0,nb)[:,None];return x
def place(dst,x,t):
 i=round(t*SR);end=min(N,i+len(x));dst[i:end]+=x[:end-i]
def captions():
 from faster_whisper import WhisperModel
 modelpath=next(Path(r'C:\Users\pc\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots').iterdir())
 model=WhisperModel(str(modelpath),device='cpu',compute_type='int8',cpu_threads=12)
 result=[];audit=[]
 cached={x['id']:x for x in json.loads((ROOT/'00_project/voice_verification.json').read_text(encoding='utf-8'))} if (ROOT/'00_project/voice_verification.json').exists() else {}
 def chars(s):return ''.join(c for c in s if '\u4e00'<=c<='\u9fff' or c.isalnum())
 for line in CFG['narration']:
  wav=OUT/'narration'/f"{line['id']}.wav"
  digest=hashlib.sha256(wav.read_bytes()).hexdigest()
  if line['id'] in cached and cached[line['id']]['similarity']>=.93 and cached[line['id']]['intended']==line['text'] and cached[line['id']].get('audio_sha256')==digest:
   from types import SimpleNamespace
   words=[SimpleNamespace(**w) for w in cached[line['id']]['words']]
  else:
   segs,info=model.transcribe(str(wav),language='zh',word_timestamps=True,beam_size=5,vad_filter=False,initial_prompt='微纳米气泡，气液传质，生态浮岛，底泥，上覆水。',condition_on_previous_text=False)
   ss=list(segs);words=[w for s in ss for w in (s.words or [])]
  recog=''.join(w.word for w in words);a=chars(line['text']);b=chars(recog)
  times=[]
  for w in words:
   cc=chars(w.word)
   for k in range(len(cc)):times.append((w.start+(w.end-w.start)*k/max(1,len(cc)),w.start+(w.end-w.start)*(k+1)/max(1,len(cc))))
  matches=difflib.SequenceMatcher(None,a,b,autojunk=False);mapping={}
  for block in matches.get_matching_blocks():
   for k in range(block.size):mapping[block.a+k]=block.b+k
  data,_=sf.read(wav);d=len(data)/SR
  aligned=[]
  for k in range(len(a)):
   j=mapping.get(k)
   if j is not None and j<len(times):aligned.append(times[j])
   else:
    kk=min(mapping,key=lambda v:abs(v-k)) if mapping else None
    if kk is not None and mapping[kk]<len(times):
     tt=times[mapping[kk]][0]+(k-kk)*d/max(1,len(a));aligned.append((max(0,tt),min(d,tt+d/max(1,len(a)))))
    else:aligned.append((k*d/max(1,len(a)),(k+1)*d/max(1,len(a))))
  chunks=[]
  for sentence in re.split('[。！？]',line['text']):
   buf=''
   for part in [p for p in re.split('[，、]',sentence) if p]:
    if buf and len(buf)+len(part)+1>21:chunks.append(buf);buf=part
    else:buf=(buf+'，'+part) if buf else part
   if buf:chunks.append(buf)
  if line['id']=='N14':chunks=['一颗气泡','一株绿植','一群躬身实干的人','改变，就从这些具体的行动开始']
  cursor=0
  for chunk in chunks:
   count=len(chars(chunk));start=aligned[cursor][0];end=aligned[min(len(aligned)-1,cursor+count-1)][1]
   result.append({'text':chunk,'startMs':round((line['start']+max(0,start-.08))*1000),'endMs':round((line['start']+min(d,end+.14))*1000),'timestampMs':None,'confidence':None})
   cursor+=count
  audit.append({'id':line['id'],'intended':line['text'],'recognized':recog,'similarity':matches.ratio(),'audio_sha256':digest,'words':[{'word':w.word,'start':w.start,'end':w.end} for w in words]})
  (ROOT/'00_project/voice_verification.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
  print(line['id'],'caption alignment',round(matches.ratio(),3),flush=True)
 # Keep phrase intervals distinct.
 result.sort(key=lambda c:c['startMs'])
 for i,c in enumerate(result[:-1]):c['endMs']=min(c['endMs'],result[i+1]['startMs'])
 (ROOT/'00_project/captions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT.parent/'studio/src/water-renewal/captions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'00_project/voice_verification.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
def mix():
 narration=np.zeros((N,2),dtype=np.float32);duck=np.ones(N,dtype=np.float32)
 for line in CFG['narration']:
  x=load(OUT/'narration'/f"{line['id']}.wav");place(narration,fade(x,.025,.07),line['start'])
  st=round(line['start']*SR);en=min(N,st+len(x));attack=int(.25*SR);release=int(.7*SR)
  duck[max(0,st-attack):st]=np.linspace(1,.36,min(st,attack))
  duck[st:en]=.36
  end=min(N,en+release);duck[en:end]=np.linspace(.36,1,end-en)
 music=np.zeros((N,2),dtype=np.float32)
 x=norm(load(OUT/'music/journey.wav'),-23.5);place(music,fade(x,2,6),0)
 x=norm(load(OUT/'music/finale.wav'),-21);place(music,fade(x,5,2),137)
 music*=duck[:,None]
 # Authentic river and bubble textures add place without masking the narrator.
 ambient=np.zeros_like(music)
 river=norm(load(Path('E:/promo_video/assets/amb_river.wav')),-37)
 for t in [0,8,12,20,85,116,123,165,177]:place(ambient,fade(river,.6,.8),t)
 bubbles=norm(load(Path('E:/promo_video/assets/amb_bubble.wav')),-32)
 place(ambient,fade(bubbles[:12*SR],.8,1),74)
 place(ambient,fade(bubbles[:4*SR],.5,.8),158)
 ambient*=np.maximum(.55,duck)[:,None]
 mix=narration+music+ambient
 # End on a clean, deliberate score cadence and reverb tail.
 mix[-3*SR:]*=np.linspace(1,0,3*SR)[:,None]
 raw=OUT/'premaster.wav';sf.write(raw,mix,SR,subtype='PCM_24')
 analysis=subprocess.run([FFMPEG,'-hide_banner','-i',str(raw),'-af','loudnorm=I=-14:TP=-1.5:LRA=10:print_format=json','-f','null','-'],capture_output=True,check=True).stderr.decode('utf-8','replace')
 stats=json.JSONDecoder().raw_decode(analysis[analysis.rfind('{'):])[0];(OUT/'loudness_analysis.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
 af=f"loudnorm=I=-14:TP=-1.5:LRA=10:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}:linear=true"
 master=ROOT.parent/'studio/public/jobs/water-renewal/master.wav'
 subprocess.run([FFMPEG,'-v','error','-y','-i',str(raw),'-af',af,'-ar',str(SR),'-c:a','pcm_s24le',str(master)],check=True)
 print('Audio master ready',flush=True)
if __name__=='__main__':
 mix();captions()
