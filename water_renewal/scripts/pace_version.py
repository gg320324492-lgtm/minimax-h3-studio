"""Export a modestly faster version from the verified full-resolution film."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ffmpeg_env import FFMPEG, FFPROBE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '07_edit/WaterRenewal_1080p.mp4'
FINAL = Path(r'C:\Users\pc\Desktop\设计短片\黑臭水体治理宣传视频\第二版成片\节奏加快版')
FINAL.mkdir(parents=True, exist_ok=True)
RATE = 1.08
FRAMES = 5500
DURATION = FRAMES / 30
outputs = {
    'master': FINAL / '让水体重新呼吸_成片2_节奏加快_高清版.mp4',
    'share': FINAL / '让水体重新呼吸_成片2_节奏加快_分享版.mp4',
}
processes = []
for kind, output in outputs.items():
    log = (ROOT / '07_edit' / f'pace_encode_{kind}.log').open('w', encoding='utf-8')
    cmd = [FFMPEG, '-hide_banner', '-y', '-i', str(SOURCE),
           '-map', '0:v:0', '-map', '0:a:0',
           '-vf', f'setpts=(PTS-STARTPTS)/{RATE},fps=30',
           '-af', f'atempo={RATE}',
           '-t', str(DURATION), '-c:v', 'libx264', '-threads', '12',
           '-preset', 'medium', '-crf', '18' if kind == 'master' else '23',
           '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
           '-color_primaries', 'bt709', '-color_trc', 'bt709',
           '-c:a', 'aac', '-b:a', '256k' if kind == 'master' else '192k',
           '-ar', '48000', '-movflags', '+faststart', str(output)]
    processes.append((kind, subprocess.Popen(cmd, stdout=log, stderr=log), log))
for kind, process, log in processes:
    code = process.wait()
    log.close()
    if code:
        raise RuntimeError(f'{kind} encode failed ({code})')
    print(kind, 'encoded', flush=True)

captions = json.loads((ROOT / '00_project/captions.json').read_text(encoding='utf-8'))
paced = [{**c, 'startMs': round(c['startMs'] / RATE),
          'endMs': round(c['endMs'] / RATE)} for c in captions]
assert all(0 <= c['startMs'] < c['endMs'] <= DURATION * 1000 for c in paced)
assert all(a['endMs'] <= b['startMs'] for a, b in zip(paced, paced[1:]))
def tc(ms):
    sec, ms = divmod(ms, 1000)
    minute, sec = divmod(sec, 60)
    hour, minute = divmod(minute, 60)
    return f'{hour:02}:{minute:02}:{sec:02},{ms:03}'
srt = '\n\n'.join(f"{i+1}\n{tc(c['startMs'])} --> {tc(c['endMs'])}\n{c['text']}"
                  for i, c in enumerate(paced)) + '\n'
(FINAL / '成片2_节奏加快_旁白字幕.srt').write_text(srt, encoding='utf-8-sig')
shutil.copy2(ROOT / '07_edit/cover.jpg', FINAL / '成片2_封面.jpg')
editorial = json.loads((ROOT / '00_project/editorial.json').read_text(encoding='utf-8'))
(FINAL / '成片2_旁白稿.txt').write_text('\n\n'.join(x['text'] for x in editorial['narration']), encoding='utf-8-sig')
(FINAL / '制作说明.md').write_text(
    '# 《让水体重新呼吸》节奏加快版\n\n'
    '全片约 3 分 3 秒，1920×1080，30 帧/秒。整体节奏提高 8%，'
    '画面、旁白、配乐与字幕同步调整；声音变速保持音高，沿用原旁白音色。\n\n'
    '保留完整叙事、柔和转场、封面及片尾呼吁：'
    '“让我们一起，共建人与自然和谐共生的美好家园！”\n', encoding='utf-8')

checks = {'pace': RATE, 'duration_seconds': DURATION, 'captions': len(paced)}
for kind, output in outputs.items():
    data = json.loads(subprocess.check_output([FFPROBE, '-v', 'error', '-show_format',
                                              '-show_streams', '-of', 'json', str(output)]))
    v = next(s for s in data['streams'] if s['codec_type'] == 'video')
    a = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    assert (v['width'], v['height'], v['r_frame_rate']) == (1920, 1080, '30/1')
    assert int(v['nb_frames']) == FRAMES
    assert abs(float(data['format']['duration']) - DURATION) < .15
    assert a['channels'] == 2 and a['sample_rate'] == '48000'
    scan = subprocess.run([FFMPEG, '-hide_banner', '-i', str(output),
                           '-vf', 'blackdetect=d=0.08:pix_th=.06',
                           '-af', 'loudnorm=I=-14:TP=-1.5:LRA=10:print_format=json',
                           '-f', 'null', '-'], capture_output=True, check=True).stderr.decode('utf-8', 'replace')
    (ROOT / '07_edit' / f'pace_qa_{kind}.log').write_text(scan, encoding='utf-8')
    loud = json.JSONDecoder().raw_decode(scan[scan.rfind('{'):])[0]
    black = [line for line in scan.splitlines() if 'black_start:' in line]
    assert not black, black
    assert abs(float(loud['input_i']) + 14) < 1
    assert float(loud['input_tp']) < 0
    checks[kind] = {'path': str(output), 'duration': float(data['format']['duration']),
                    'size_mb': round(output.stat().st_size / 1e6, 1),
                    'loudness_lufs': loud['input_i'], 'true_peak_db': loud['input_tp'],
                    'frames': int(v['nb_frames']), 'black_events': black}
    print(kind, 'verified', flush=True)

# Check the encoded speech, including the recently added words.
clip = ROOT / '07_edit/paced_final_call.wav'
subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', str(185.8 / RATE),
                '-i', str(outputs['master']), '-t', '6', '-vn', '-ar', '24000', str(clip)], check=True)
from faster_whisper import WhisperModel
snapshot = next(Path(r'C:\Users\pc\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots').iterdir())
model = WhisperModel(str(snapshot), device='cpu', compute_type='int8', cpu_threads=8)
segments, _ = model.transcribe(str(clip), language='zh', condition_on_previous_text=False)
spoken = ''.join(s.text for s in segments)
assert '我们一起' in spoken or '我們一起' in spoken, spoken
checks['final_call'] = {'recognized': spoken, 'call_to_action_spoken': True}
for sec in [0, 24.4 / RATE, 189 / RATE, DURATION - .5]:
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', str(sec),
                    '-i', str(outputs['master']), '-frames:v', '1', '-q:v', '2',
                    str(ROOT / '07_edit' / f'paced_qa_{sec:.1f}.jpg')], check=True)
(FINAL / '验收记录.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / '00_project/pace_version.json').write_text(
    json.dumps({**checks, 'caption_timing': paced}, ensure_ascii=False, indent=2), encoding='utf-8')
preview = ROOT.parent / 'studio/public/jobs/water-renewal/paced_108.mp4'
shutil.copy2(outputs['share'], preview)
print('Paced version complete', flush=True)
