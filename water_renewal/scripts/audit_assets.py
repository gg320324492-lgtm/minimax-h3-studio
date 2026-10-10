import json, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG, FFPROBE
ROOT=Path(r'C:\Users\pc\Desktop\设计短片\黑臭水体治理宣传视频')
OUT=Path(__file__).resolve().parents[1]/'01_reference'
OUT.mkdir(parents=True,exist_ok=True)
FONT=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
assets=[]
for batch in ['第一批素材','第二批素材']:
    for i,p in enumerate(sorted((ROOT/batch).iterdir()),1):
        a={'id':('A' if batch=='第一批素材' else 'B')+f'{i:02}', 'path':str(p),'batch':batch,'kind':'video' if p.suffix=='.mp4' else 'image'}
        if a['kind']=='video':
            data=json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',str(p)]))
            v=next(s for s in data['streams'] if s['codec_type']=='video')
            a.update(duration=float(data['format']['duration']),width=v['width'],height=v['height'],fps=v['r_frame_rate'],audio=any(s['codec_type']=='audio' for s in data['streams']))
        else:
            with Image.open(p) as im:a.update(width=im.width,height=im.height)
        assets.append(a)
original=next(ROOT.glob('成片*.mp4'))
data=json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_format','-show_streams','-of','json',str(original)]))
(OUT/'original_metadata.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'inventory.json').write_text(json.dumps(assets,ensure_ascii=False,indent=2),encoding='utf-8')
def frame(p,t,out):
    subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(p),'-frames:v','1','-vf','scale=640:-1',str(out)],check=True)
def thumb(a):
    p=OUT/(a['id']+'.jpg')
    if a['kind']=='video':frame(a['path'],min(3,a['duration']*.35),p)
    else:
        with Image.open(a['path']) as im:ImageOps.exif_transpose(im).convert('RGB').resize((640,round(im.height*640/im.width))).save(p)
    return p
with ThreadPoolExecutor(4) as pool:list(pool.map(thumb,assets))
def sheet(rows,name,cols=4):
    w,h=400,274
    canvas=Image.new('RGB',(cols*w,((len(rows)+cols-1)//cols)*h),'#17242e');d=ImageDraw.Draw(canvas)
    for i,(p,label) in enumerate(rows):
        im=Image.open(p);im.thumbnail((w-12,h-42));x=(i%cols)*w;y=(i//cols)*h
        canvas.paste(im,(x+(w-im.width)//2,y+(h-42-im.height)//2));d.text((x+8,y+h-36),label,font=FONT,fill='white')
    canvas.save(OUT/name)
for batch in ['第一批素材','第二批素材']:
    aa=[a for a in assets if a['batch']==batch]
    sheet([(OUT/(a['id']+'.jpg'),f"{a['id']}  {a.get('duration',0):.1f}s  {a['width']}×{a['height']}") for a in aa],batch+'.jpg')
duration=float(data['format']['duration'])
times=list(range(0,int(duration),5))
for part in range(0,len(times),24):
    rows=[]
    for t in times[part:part+24]:
        p=OUT/f'original_{t:03}.jpg';frame(original,t,p);rows.append((p,f'成片1  {t}s'))
    sheet(rows,f'original_sheet_{part//24}.jpg')
print(json.dumps({'original':str(original),'duration':duration,'assets':len(assets),'videos':[(a['id'],a['duration']) for a in assets if a['kind']=='video']},ensure_ascii=False))
