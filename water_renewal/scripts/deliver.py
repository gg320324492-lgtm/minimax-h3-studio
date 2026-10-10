import json,sys,subprocess,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG,FFPROBE
ROOT=Path(__file__).resolve().parents[1]
FINAL=Path(r'C:\Users\pc\Desktop\设计短片\黑臭水体治理宣传视频\第二版成片')
FINAL.mkdir(parents=True,exist_ok=True)
src=ROOT/'07_edit/WaterRenewal_1080p.mp4'
master=FINAL/'让水体重新呼吸_成片2_全面升级_高清版.mp4'
share=FINAL/'让水体重新呼吸_成片2_全面升级_分享版.mp4'
shutil.copy2(src,master)
subprocess.run([FFMPEG,'-v','error','-y','-i',str(master),'-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','medium','-crf','23','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-c:a','aac','-b:a','192k','-movflags','+faststart',str(share)],check=True)
captions=json.loads((ROOT/'00_project/captions.json').read_text(encoding='utf-8'))
def tc(ms):
 ms=int(ms);s,ms=divmod(ms,1000);m,s=divmod(s,60);h,m=divmod(m,60);return f'{h:02}:{m:02}:{s:02},{ms:03}'
srt='\n\n'.join(f"{i+1}\n{tc(c['startMs'])} --> {tc(c['endMs'])}\n{c['text']}" for i,c in enumerate(captions))+'\n'
(FINAL/'成片2_旁白字幕.srt').write_text(srt,encoding='utf-8-sig')
shutil.copy2(ROOT/'README.md',FINAL/'制作说明.md')
shutil.copy2(ROOT/'07_edit/cover.jpg',FINAL/'成片2_封面.jpg')
lines=json.loads((ROOT/'00_project/editorial.json').read_text(encoding='utf-8'))['narration']
(FINAL/'成片2_旁白稿.txt').write_text('\n\n'.join(l['text'] for l in lines),encoding='utf-8-sig')
checks={}
for name,p in [('master',master),('share',share)]:
 data=json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',str(p)]))
 v=next(s for s in data['streams'] if s['codec_type']=='video');a=next(s for s in data['streams'] if s['codec_type']=='audio')
 assert (v['width'],v['height'])==(1920,1080)
 assert v['pix_fmt']=='yuv420p' and v['r_frame_rate']=='30/1' and v['color_space']=='bt709'
 assert abs(float(data['format']['duration'])-198)<.15
 assert a['channels']==2 and a['sample_rate']=='48000'
 scan=subprocess.run([FFMPEG,'-hide_banner','-i',str(p),'-vf','blackdetect=d=0.08:pix_th=.06','-af','loudnorm=I=-14:TP=-1.5:LRA=10:print_format=json','-f','null','-'],capture_output=True,check=True).stderr.decode('utf-8','replace')
 (ROOT/'07_edit'/f'qa_{name}.log').write_text(scan,encoding='utf-8')
 loud=json.JSONDecoder().raw_decode(scan[scan.rfind('{'):])[0];black=[l for l in scan.splitlines() if 'black_start:' in l]
 assert not black,black
 assert abs(float(loud['input_i'])+14)<1.0,loud
 checks[name]={'path':str(p),'duration':float(data['format']['duration']),'size_mb':round(p.stat().st_size/1e6,1),'width':v['width'],'height':v['height'],'fps':v['r_frame_rate'],'pixel_format':v['pix_fmt'],'color_space':v['color_space'],'loudness_lufs':loud['input_i'],'true_peak_db':loud['input_tp'],'black_events':black}
 print(name,checks[name]['size_mb'],'MB verified',flush=True)
(ROOT/'07_edit/delivery_qa.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
(FINAL/'验收记录.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
