import sys, json, shutil, time
from pathlib import Path
REPO=Path('E:/Minimax-H3/liaozhai_demo/ACE-Step-1.5')
sys.path.insert(0,str(REPO))
OUT=Path(__file__).resolve().parents[1]/'05_audio/music'
OUT.mkdir(parents=True,exist_ok=True)
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams,GenerationConfig,generate_music
handler=AceStepHandler()
msg,ok=handler.initialize_service(project_root=str(REPO),config_path='acestep-v15-turbo',device='auto',offload_to_cpu=False)
if not ok:raise RuntimeError(msg)
lm=LLMHandler()
msg,ok=lm.initialize(checkpoint_dir=str(REPO/'checkpoints'),lm_model_path='acestep-5Hz-lm-1.7B',backend='pt',device='auto',offload_to_cpu=False)
if not ok:raise RuntimeError(msg)
prompts=[
 ('journey',144,202610101,'Instrumental cinematic environmental documentary underscore, contemporary orchestral film score, gentle piano motif, warm cello, soft evolving strings, restrained reflective opening gradually growing into a steady purposeful rhythm, delicate mallet pulse, subtle percussion, inspiring hopeful atmosphere, polished studio recording, spacious, no vocals, no singing, 84 bpm, D major'),
 ('finale',64,202610102,'Instrumental uplifting orchestral documentary finale, a noble warm soaring memorable strings melody, resonant French horns, broad lush symphonic strings, piano, rhythmic timpani and cinematic drums, emotional crescendo building to a triumphant dignified optimistic climax, heroic environmental public service film, hopeful not aggressive, resolving strong final D major chord with natural reverb tail, no vocals, no singing, 84 bpm, D major')
]
for name,dur,seed,caption in prompts:
    if (OUT/(name+'.wav')).exists():continue
    t=time.time()
    p=GenerationParams(task_type='text2music',thinking=False,caption=caption,lyrics='[Instrumental]',instrumental=True,duration=dur,inference_steps=8,seed=seed)
    c=GenerationConfig(batch_size=1,use_random_seed=False,audio_format='wav')
    result=generate_music(handler,lm,p,c,save_dir=str(OUT/'raw'))
    files=[a['path'] for a in result.audios if a.get('path')]
    if not files:raise RuntimeError(str(result))
    shutil.copy2(files[0],OUT/(name+'.wav'))
    print(name,'generated',round(time.time()-t,1),flush=True)
(OUT/'provenance.json').write_text(json.dumps({'model':'ACE-Step 1.5 turbo','prompts':prompts},ensure_ascii=False,indent=2),encoding='utf-8')
