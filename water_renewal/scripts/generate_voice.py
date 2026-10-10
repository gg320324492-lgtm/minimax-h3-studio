import json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG,FFPROBE
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'00_project/editorial.json').read_text(encoding='utf-8'))
OUT=ROOT/'05_audio/narration'
OUT.mkdir(parents=True,exist_ok=True)
def duration(p):return float(subprocess.check_output([FFPROBE,'-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]))
def main():
    import torch, soundfile as sf
    from qwen_tts import Qwen3TTSModel
    torch.manual_seed(20261010)
    model=None
    if any(not (OUT/(l['id']+'_raw.wav')).exists() for l in CFG['narration']):
        model=Qwen3TTSModel.from_pretrained('E:/tts/models/Qwen3-TTS-1.7B-CustomVoice',device_map='cuda:0',dtype=torch.bfloat16)
    base='标准普通话，成熟男声，纪录片解说，声音沉稳温暖、清晰饱满。中等语速，语句连贯，停顿自然，不拖长字音。'
    manifest=[]
    for line in CFG['narration']:
        raw=OUT/(line['id']+'_raw.wav');final=OUT/(line['id']+'.wav')
        if not raw.exists():
            t=time.time()
            instruct=base+('带着坚定的信念与向上的力量，逐渐昂扬，最后一句有充满希望的号召感。' if int(line['id'][1:])>=14 else '真诚、克制，像在讲述真实的现场行动。')
            wavs,sr=model.generate_custom_voice(text=line['text'],language='Chinese',speaker='Uncle_Fu',instruct=instruct,max_new_tokens=1024,do_sample=True,temperature=0.65,top_p=0.9)
            sf.write(str(raw),wavs[0],sr)
            print(line['id'],round(time.time()-t,1),'sec generation',flush=True)
        trim=OUT/(line['id']+'_trim.wav')
        subprocess.run([FFMPEG,'-v','error','-y','-i',str(raw),'-af','silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,areverse',str(trim)],check=True)
        d=duration(trim);speed=max(0.94,d/line['slot'])
        if speed>1.3:print('LONG LINE',line['id'],d,speed,flush=True)
        subprocess.run([FFMPEG,'-v','error','-y','-i',str(trim),'-af',f'atempo={speed:.5f},highpass=f=75,equalizer=f=2800:t=q:w=1:g=1.2,loudnorm=I=-17:TP=-2:LRA=8','-ar','48000','-ac','1',str(final)],check=True)
        manifest.append({**line,'file':str(final),'duration':duration(final),'speed':speed})
        (ROOT/'00_project/voice_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        print(line['id'],'duration',duration(final),'speed',speed,flush=True)
main()
