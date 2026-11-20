"""Promo narration TTS via local Kokoro-82M (zm_yunyang, documentary male).

Outputs 48k AAC per line + narration_manifest.json with measured durations,
so the timeline builder can lay scenes around real narration lengths.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
    sys.path.insert(0, r'E:\Minimax-H3\scripts')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()

PROJECT = Path(r'E:/Minimax-H3/productions/water_renewal')
OUT = PROJECT / 'assets' / 'narration'
OUT.mkdir(parents=True, exist_ok=True)

VOICE = 'zm_yunyang'
SPEED = 0.97  # calm but not dragging; keeps total film ≈122s

# (slug, text)
LINES = [
    ('N01', '当水体失去流动与活力，黑臭、淤积和污染问题，也随之出现。'),
    ('N02', '在真实水环境中，问题往往并不单一。上覆水、底泥、污染输入与水动力相互作用，构成了复杂的治理现场。'),
    ('N03', '面对这样的水体，治理从来不是把设备简单放进河里。从现场调查、方案论证，到工艺设计，每一步都需要回到具体问题本身。'),
    ('N04', '针对黑臭水体治理，团队将微纳米气泡技术与工程装备结合，开展现场试验和系统验证。'),
    ('N05', '相较于普通大气泡，微纳米气泡具有更小的尺度和更高的气液传质效率，为增氧、强化氧化和污染控制提供新的技术路径。'),
    ('N06', '治理首先从现场开始。清理漂浮物、排查污染输入、整理作业区域，为后续系统运行创造条件。'),
    ('N07', '随后，团队完成输送管线和曝气单元布设，根据河道条件不断调整作用位置与运行参数。'),
    ('N08', '设备启动后，微纳米气泡被持续输送进入水体。肉眼可见的白色气泡云，在水下不断扩散，而真正发生的，是气、水以及污染物之间持续的界面作用。'),
    ('N09', '从一台设备，到整段河道，工程化意味着技术必须适应真实环境，稳定运行，并接受现场检验。'),
    ('N10', '团队同时关注底泥与上覆水之间的污染物迁移，研究臭氧微纳米气泡对污染物去除、释放抑制及界面氧化过程的影响。'),
    ('N11', '从机理研究，到装备开发，再到现场验证，我们试图回答的不只是能不能做，更是怎样把它做得稳定、可验证、可工程化。'),
    ('N12', '从一颗微小气泡，到一条真实河道。让技术，参与水环境的重新呼吸。'),
]


def dur_of(path: Path) -> float:
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', str(path)],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def main():
    from kokoro import KPipeline
    import soundfile as sf

    print('Loading Kokoro-82M ...', flush=True)
    pipeline = KPipeline(lang_code='z', model=True, repo_id='hexgrad/Kokoro-82M')
    print('ready', flush=True)

    manifest = []
    for slug, text in LINES:
        wav = Path(f'E:/Minimax-H3/out/tmp/kokoro_{slug}.wav')
        m4a = OUT / f'{slug}.m4a'
        t0 = time.time()
        chunks = []
        for _gs, _ps, a in pipeline(text, voice=VOICE, speed=SPEED):
            if a is not None and len(a) > 0:
                chunks.append(a)
        import numpy as np
        full = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        sf.write(str(wav), full, 24000)
        subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav),
            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
            '-ar', '48000', '-ac', '2', '-c:a', 'aac', '-b:a', '192k', str(m4a),
        ], check=True)
        d = dur_of(m4a)
        manifest.append({'slug': slug, 'text': text, 'file': str(m4a), 'duration': round(d, 3)})
        print(f'  {slug}: {d:.2f}s  {text[:18]}...  ({time.time()-t0:.1f}s)', flush=True)

    (PROJECT / 'work' / 'narration_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    total = sum(m['duration'] for m in manifest)
    print(f'TOTAL narration: {total:.1f}s')


if __name__ == '__main__':
    main()
