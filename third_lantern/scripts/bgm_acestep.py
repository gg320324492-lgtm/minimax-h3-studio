"""Generate gufeng ambient BGM candidates for third_lantern (ACE-Step 1.5).

Arc: sparse guqin harmonics + low drone (mystery) -> subtle tension ->
xiao flute / warm strings resolve (tender farewell).

Run from repo root:
  cd ACE-Step-1.5 && acestep-env/Scripts/python.exe ../scripts/bgm_acestep.py
"""
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/third_lantern')
REPO = Path(r'E:/Minimax-H3/liaozhai_demo/ACE-Step-1.5')
sys.path.insert(0, str(REPO))

SEEDS = [411, 715, 924]
CAPTION = ('Chinese gufeng ambient film score, sparse guqin harmonics, xiao flute, '
           'low soft drone, mysterious and quiet beginning, gradually turning warm '
           'and tender, emotional strings ending, melancholic, slow, very sparse, '
           'no drums, no percussion, instrumental')
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
    lm = LLMHandler()
    msg, ok = lm.initialize(checkpoint_dir=str(REPO / 'checkpoints'),
                            lm_model_path='acestep-5Hz-lm-1.7B',
                            backend='pt', device='auto', offload_to_cpu=False)
    if not ok:
        print('LM init failed:', msg)
        sys.exit(1)
    print(f'loaded {time.time()-t0:.0f}s')

    results = []
    for seed in SEEDS:
        params = GenerationParams(
            task_type='text2music', thinking=False,
            caption=CAPTION, lyrics='[Instrumental]', instrumental=True,
            duration=160, inference_steps=8, seed=seed)
        cfg = GenerationConfig(batch_size=1, use_random_seed=False, audio_format='wav')
        t0 = time.time()
        r = generate_music(dit, lm, params, cfg, save_dir=str(OUT))
        for a in r.audios:
            if a.get('path'):
                results.append(a['path'])
                print(f'seed {seed}: {a["path"]} ({time.time()-t0:.0f}s)')

    import numpy as np
    from scipy.io import wavfile
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for p in results:
        wav = Path(p)
        sr, data = wavfile.read(str(wav))
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float64)
        data /= (np.max(np.abs(data)) or 1.0)
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.specgram(data, NFFT=2048, Fs=sr, noverlap=1024, cmap='magma')
        ax.set_title(wav.stem[:8])
        fig.tight_layout()
        fig.savefig(str(OUT / f'{wav.stem}_spec.png'), dpi=80)
        plt.close(fig)
        print('spec:', wav.stem[:8])


if __name__ == '__main__':
    main()
