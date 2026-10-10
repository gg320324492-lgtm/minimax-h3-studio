import json,subprocess,sys,shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps,ImageEnhance
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'studio/public/jobs/water-renewal'
OUT.mkdir(parents=True,exist_ok=True)
assets=json.loads((ROOT/'01_reference/inventory.json').read_text(encoding='utf-8'))
def work(a):
    p=Path(a['path']);o=OUT/(a['id']+('.mp4' if a['kind']=='video' else '.jpg'))
    if o.exists():return
    if a['kind']=='image':
        with Image.open(p) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((3200,2400))
            im=ImageEnhance.Contrast(im).enhance(1.025)
            im=ImageEnhance.Color(im).enhance(1.045)
            im.save(o,quality=94,subsampling=0)
    else:
        vf='fps=30,setsar=1'
        if a['id']=='A03':vf+=',tpad=stop_mode=clone:stop_duration=0.25'
        subprocess.run([FFMPEG,'-v','error','-y','-i',str(p),'-vf',vf,'-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',str(o)],check=True)
with ThreadPoolExecutor(4) as pool:list(pool.map(work,assets))
for name,src in [('micro.mp4','E:/promo_video/assets/h3/H3A_1080.mp4'),('interface.mp4','E:/promo_video/assets/h3/H3B_1080.mp4')]:
    shutil.copy2(src,OUT/name)
print('Prepared',len(assets),'source assets + clean mechanism animations',flush=True)
