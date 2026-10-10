from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'studio/src/water-renewal'
for name in ['OpeningScene','FieldScene','BubbleScene','EcologyScene','ValidationScene','FinaleScene']:
 p=ROOT/(name+'.tsx');s=p.read_text(encoding='utf-8')
 if "import {BlendSequence}" not in s:
  s="import {BlendSequence} from './Design';\n"+s
 s=s.replace('<Sequence ','<BlendSequence ').replace('</Sequence>','</BlendSequence>')
 if name=='OpeningScene':
  s=s.replace('<BlendSequence from={0} durationInFrames={90}>','<BlendSequence from={0} durationInFrames={90} fadeIn={false}>')
  s=s.replace('<Eyebrow index="01"','<Eyebrow duration={360} index="01"')
  s=s.replace('<BlendSequence from={360} durationInFrames={360}>','<BlendSequence from={360} durationInFrames={360} blend={28}>')
 else:
  durations={'FieldScene':750,'BubbleScene':1110,'EcologyScene':1380,'ValidationScene':780}
  if name in durations:s=s.replace('<Eyebrow index=',f'<Eyebrow duration={{{durations[name]}}} index=')
  s=s.replace('<BlendSequence from={0} durationInFrames=', '<BlendSequence from={0} blend={28} durationInFrames=')
 p.write_text(s,encoding='utf-8')
p=ROOT/'Film.tsx';s=p.read_text(encoding='utf-8')
for a,b in [(720,750),(750,780),(1110,1140),(1380,1410),(780,810)]:
 # Match each existing parent sequence through its start to avoid rewriting a previous result.
 pass
for start,length in [(0,720),(720,750),(1470,1110),(2580,1380),(3960,780)]:
 s=s.replace(f'from={{{start}}} durationInFrames={{{length}}}',f'from={{{start}}} durationInFrames={{{length+30}}}')
p.write_text(s,encoding='utf-8')
print('Picture overlaps enabled; narration timing preserved.')
