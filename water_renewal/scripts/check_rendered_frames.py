import sys, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG

root = Path(__file__).resolve().parents[1]
movie = root / '07_edit/WaterRenewal_1080p.mp4'
out = root / '07_edit/rendered_frames'
out.mkdir(exist_ok=True)
times = [0, 3.3, 12.4, 24.4, 28, 39, 49.5, 56, 68, 77,
         86.5, 93, 101, 112, 117, 125, 132.5, 140, 151, 158.5,
         162.5, 170, 182, 189, 197.5]
sheet = Image.new('RGB', (2400, 1475), '#071e2a')
draw = ImageDraw.Draw(sheet)
for i, sec in enumerate(times):
    path = out / f'{sec:06.1f}.jpg'
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', str(sec), '-i', str(movie),
                    '-frames:v', '1', '-q:v', '2', str(path)], check=True)
    im = Image.open(path).convert('RGB').resize((480, 270))
    x, y = (i % 5) * 480, (i // 5) * 295
    sheet.paste(im, (x, y))
    draw.text((x+10, y+275), f'{int(sec//60):02}:{sec%60:04.1f}', fill='white')
sheet.save(root / '07_edit/rendered_review.jpg', quality=93)
print('Final movie frames extracted for review', flush=True)

# Verify the actual encoded movie speaks the newly requested call to action.
audio = out / 'final_call.wav'
subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', '185.8', '-i', str(movie),
                '-t', '6', '-vn', '-ar', '24000', str(audio)], check=True)
from faster_whisper import WhisperModel
snapshot = next(Path(r'C:\Users\pc\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots').iterdir())
model = WhisperModel(str(snapshot), device='cpu', compute_type='int8', cpu_threads=8)
segments, _ = model.transcribe(str(audio), language='zh', condition_on_previous_text=False)
spoken = ''.join(s.text for s in segments)
has_call = '我们一起' in spoken or '我們一起' in spoken
assert has_call, spoken
(root / '07_edit/encoded_voice_check.json').write_text(
    json.dumps({'recognized': spoken, 'call_to_action_spoken': has_call}, ensure_ascii=False, indent=2), encoding='utf-8')
print('Call to action confirmed in encoded movie audio', flush=True)
