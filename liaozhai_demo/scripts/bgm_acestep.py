"""Generate gufeng-suspense BGM candidates with ACE-Step 1.5 (MIT).

Run from repo root via env python:
  cd ACE-Step-1.5 && E:/Minimax-H3/liaozhai_demo/acestep-env/Scripts/python.exe \
      E:/Minimax-H3/liaozhai_demo/scripts/bgm_acestep.py

Produces N seeded 90s instrumental candidates in 05_audio/BGM/candidates/,
plus a spectrogram png per candidate for visual QC.
"""
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
REPO = PROJECT / 'ACE-Step-1.5'
sys.path.insert(0, str(REPO))

SEEDS = [731, 2026, 924]
CAPTION = ('Chinese classical gufeng horror film score, guzheng plucks, erhu, dizi flute, '
           'pentatonic minor, tense eerie suspense, dark slow sparse, low drone, '
           'no drums, instrumental')

OUT = PROJECT / '05_audio' / 'BGM' / 'candidates'


def main():
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=str(REPO), config_path='acestep-v15-turbo',
                                     device='auto', offload_to_cpu=False)
    if not ok:
        print('DiT init failed:', msg)
        sys.exit(1)
    print(f'DiT loaded {time.time()-t0:.0f}s')

    t0 = time.time()
    lm = LLMHandler()
    msg, ok = lm.initialize(checkpoint_dir=str(REPO / 'checkpoints'),
                            lm_model_path='acestep-5Hz-lm-1.7B',
                            backend='pt', device='auto', offload_to_cpu=False)
    if not ok:
        print('LM init failed:', msg)
        sys.exit(1)
    print(f'LM loaded {time.time()-t0:.0f}s')

    params = GenerationParams(
        task_type='text2music', thinking=False,
        caption=CAPTION, lyrics='[Instrumental]', instrumental=True,
        duration=90, inference_steps=8, seed=SEEDS[0])
    cfg = GenerationConfig(batch_size=len(SEEDS), use_random_seed=False,
                           audio_format='wav')
    # one generation per seed so each candidate is reproducible
    results = []
    for i, seed in enumerate(SEEDS):
        params.seed = seed
        t0 = time.time()
        r = generate_music(dit, lm, params, cfg, save_dir=str(OUT))
        paths = [a['path'] for a in r.audios if a.get('path')]
        results += paths
        print(f'seed {seed}: {paths} ({time.time()-t0:.0f}s)')

    # spectrograms for visual QC
    for p in results:
        wav = Path(p)
        png = OUT / f'{wav.stem}_spec.png'
        subprocess_spec(wav, png)
        print('spec:', png.name)


def subprocess_spec(wav, png):
    import numpy as np
    from scipy.io import wavfile
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sr, data = wavfile.read(str(wav))
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float32) / 32768.0
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.specgram(data, NFFT=2048, Fs=sr, noverlap=1024, cmap='magma',
                vmin=-120, vmax=-20)
    ax.set_title(wav.name)
    fig.tight_layout()
    fig.savefig(str(png), dpi=80)
    plt.close(fig)


if __name__ == '__main__':
    main()
