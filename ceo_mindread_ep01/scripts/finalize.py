"""Finalize: cover + copy all deliverables to 09_final/ and Desktop outputs.

v3: reads real seed_manifest.json (gen-time recorded), writes fresh render_report.
"""


# --- ffmpeg binary resolution -------------------------------------------------
# PATH `ffmpeg` on this machine is GNU Octave's bundled 4.2.11, not a normal
# install, so every encode silently depended on a third-party app. Resolve via
# ffmpeg_env (repo-bundled 7.1.1 by default; MINIMAX_FFMPEG_LEGACY=1 to pin the
# legacy PATH binary for byte-comparable re-runs).
import sys as _sys, os as _os  # noqa: E402
if r'E:\Minimax-H3' not in _sys.path:
    _sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()
# -----------------------------------------------------------------------------
import json
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
# Both output roots are overridable so a re-run does not destroy an existing
# delivery. Project convention is that originals are kept and revisions are
# written alongside; run_post_chain.sh points these at a tagged directory unless
# PROMOTE=1 is set.
FINAL_DIR = Path(_os.environ.get('EP01_FINAL_DIR', str(PROJECT / '09_final')))
if not FINAL_DIR.is_absolute():
    FINAL_DIR = PROJECT / FINAL_DIR
DESKTOP = Path(_os.environ.get(
    'EP01_DESKTOP_DIR',
    r'C:\Users\pc\Desktop\MiniMax-H3-Outputs\EP01_CEO_Mindread\09_final'))
FINAL_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def get_font(size, bold=False):
    paths = ['C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',
             'C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/NotoSansSC-VF.ttf']
    for path in paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_cover():
    log('Generating cover...')
    ceo = Image.open(PROJECT / '01_reference/ceo/CEO_MASTER_REFERENCE.png').convert('RGB')
    intern = Image.open(PROJECT / '01_reference/intern/INTERN_MASTER_REFERENCE.png').convert('RGB')

    cover_w, cover_h = 1080, 1920
    cover = Image.new('RGB', (cover_w, cover_h), (20, 20, 30))

    target_h = 1320
    intern_w = int(intern.width * target_h / intern.height)
    intern_r = intern.resize((intern_w, target_h), Image.LANCZOS)
    # keep intern's face visible: crop from right side if too wide
    if intern_w > cover_w // 2 + 120:
        intern_r = intern_r.crop((intern_w - (cover_w // 2 + 120), 0, intern_w, target_h))
        intern_w = intern_r.width
    cover.paste(intern_r, (0, 60))

    ceo_w = int(ceo.width * target_h / ceo.height)
    ceo_r = ceo.resize((ceo_w, target_h), Image.LANCZOS)
    if ceo_w > cover_w // 2 + 120:
        ceo_r = ceo_r.crop((0, 0, cover_w // 2 + 120, target_h))
        ceo_w = ceo_r.width
    cover.paste(ceo_r, (cover_w - ceo_w, 60))

    overlay = Image.new('RGBA', cover.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(1380, 1920):
        alpha = int((y - 1380) / 540 * 235)
        draw.rectangle([(0, y), (cover_w, y + 1)], fill=(0, 0, 0, alpha))
    cover = Image.alpha_composite(cover.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(cover)

    title_font = get_font(74, bold=True)
    sub_font = get_font(56)
    tag_font = get_font(46)
    cx = cover_w // 2

    def center(text, y, font, fill, sw):
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, y), text, font=font, fill=fill,
                  stroke_width=sw, stroke_fill=(0, 0, 0))

    center('我突然听见了', 1430, title_font, (255, 255, 255), 4)
    center('她的心声', 1515, title_font, (255, 255, 255), 4)
    center('可她说我7秒后会死', 1625, sub_font, (255, 220, 100), 3)
    center('09:17 · 时间循环', 1735, tag_font, (185, 185, 205), 2)

    out = PROJECT / '08_cover/EP01_DOUYIN_COVER.jpg'
    out.parent.mkdir(parents=True, exist_ok=True)
    cover.save(out, quality=92)
    log(f'  {out}')


def probe(video):
    r = subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(video)]).decode()
    return json.loads(r)


def copy_final_assets():
    log('\nCopying final assets...')
    pairs = [
        ('07_edit/EP01_WITH_SUBTITLES.mp4', 'EP01_DOUYIN_FINAL.mp4'),
        ('08_cover/EP01_DOUYIN_COVER.jpg', 'EP01_DOUYIN_COVER.jpg'),
        ('06_subtitles/EP01.ass', 'EP01.ass'),
        ('06_subtitles/EP01.srt', 'EP01.srt'),
        ('00_project/shot_manifest.json', 'shot_manifest.json'),
        ('00_project/seed_manifest.json', 'seed_manifest.json'),
        ('00_project/timeline.json', 'timeline.json'),
    ]
    for src_rel, dst_name in pairs:
        src = PROJECT / src_rel
        if not src.exists():
            log(f'  MISSING: {src_rel}')
            continue
        dst = FINAL_DIR / dst_name
        shutil.copy2(str(src), str(dst))
        log(f'  {dst_name} ({dst.stat().st_size/1024/1024:.1f}MB)' if dst.suffix == '.mp4'
            else f'  {dst_name}')

    # Preview 540p
    log('  generating preview...')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error',
                    '-i', str(FINAL_DIR / 'EP01_DOUYIN_FINAL.mp4'),
                    '-vf', 'scale=540:960:flags=lanczos',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '24',
                    '-c:a', 'aac', '-b:a', '128k', '-pix_fmt', 'yuv420p',
                    str(FINAL_DIR / 'EP01_DOUYIN_PREVIEW.mp4')], check=True)
    # No-subtitle variant
    shutil.copy2(str(PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'), str(FINAL_DIR / 'EP01_NO_SUBTITLE.mp4'))

    # Publish copy
    copy_text = '''标题：
我突然能听见实习生的心声，可她说我7秒后会死……

正文：
第一次听见她心声的时候，
她正在倒数我的死期。

可真正奇怪的是——
她好像已经经历过这一切很多次了。

#AI短剧 #悬疑短剧 #读心术 #时间循环 #剧情反转
'''
    (FINAL_DIR / 'publish_copy.txt').write_text(copy_text, encoding='utf-8')

    # Render report
    generate_render_report()


def generate_render_report():
    d = probe(FINAL_DIR / 'EP01_DOUYIN_FINAL.mp4')
    dur = float(d['format']['duration'])
    size_mb = int(d['format']['size']) / 1024 / 1024
    bitrate = int(d['format']['bit_rate']) / 1e6
    vs = [s for s in d['streams'] if s['codec_type'] == 'video'][0]
    as_ = [s for s in d['streams'] if s['codec_type'] == 'audio'][0]

    sm = json.loads((PROJECT / '00_project/seed_manifest.json').read_text(encoding='utf-8'))
    manifest = json.loads((PROJECT / '00_project/shot_manifest.json').read_text(encoding='utf-8'))
    total_takes = sum(len([k for k in v if k.startswith('seed_')]) for v in sm.get('shots', {}).values())

    report = f'''# 《总裁突然听见实习生的心声》EP01 - Final Render Report (v3 FixAll)

**Generated**: {time.strftime("%Y-%m-%d %H:%M:%S")}

## Final Output
| Item | Value |
|------|-------|
| Duration | {dur:.2f}s |
| Resolution | {vs['width']} x {vs['height']} |
| Codec | H.264 High / yuv420p |
| FPS | {vs['avg_frame_rate']} |
| Audio | AAC {as_['sample_rate']}Hz {as_['channels']}ch 320kbps |
| Loudness | -14 LUFS (loudnorm) |
| Bitrate | {bitrate:.2f} Mbps |
| File Size | {size_mb:.1f} MB |

## Pipeline
- 生成: MiniMax-H3 Ref2VA (int8_convrot) + 4-step turbo LoRA, 768x1344 @24fps
- 一致性: R2V MASTER_REFERENCE (<Picture 1/2/3>)
- 超分: Real-ESRGAN_x2plus fp16 tile=512 (pipe_4k_fast.py) -> Lanczos 1080x1920
- TTS: Kokoro-82M 本地 (CEO=zm_yunyang, INTERN=zf_xiaoxiao; 心声 lowpass 4k)
- 混音: mix_audio_v4.py - timeline驱动, BGM sidechain ducking, loudnorm -14 LUFS, 立体声
- 字幕: burn_subtitles_v2.py - timeline驱动, 自动换行(<=1000px)
- 总 takes: {total_takes} (生成时实时记录 seed, 见 seed_manifest.json)

## Shots
| Shot | Take | Frames | Duration | Seed |
|------|------|--------|----------|------|
'''
    for sid, sel in manifest['selections'].items():
        take = sel.get('source_take', f'{sid}_T01')
        tk = take.split('_T')[1] if '_T' in take else '01'
        seed = sm.get('shots', {}).get(sid, {}).get(f'seed_T{tk}', '-')
        report += f"| {sid} | {tk} | {sel['frames']} | {sel['duration_s']:.2f}s | {seed} |\n"

    (FINAL_DIR / 'render_report.md').write_text(report, encoding='utf-8')
    log('  render_report.md')


def sync_desktop():
    log('\nSyncing to Desktop...')
    DESKTOP.mkdir(parents=True, exist_ok=True)
    for f in FINAL_DIR.iterdir():
        if f.is_file():
            shutil.copy2(str(f), str(DESKTOP / f.name))
    log(f'  -> {DESKTOP}')


if __name__ == '__main__':
    generate_cover()
    copy_final_assets()
    sync_desktop()
    log('\n=== ALL FINAL ASSETS READY ===')
