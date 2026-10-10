import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence,OffthreadVideo} from 'remotion';
import {Shot,Label,Eyebrow,Statement,PrincipleBadge,asset,SplitMontage} from './Design';
export const ValidationScene:React.FC=()=> <AbsoluteFill>
 <BlendSequence from={0} blend={28} durationInFrames={240}>
 <OffthreadVideo src={asset('interface.mp4')} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/>
 <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,24,30,.82),rgba(3,24,30,.15))'}}/>
 <Statement top={348} small="底泥与上覆水" lines={['看向水面之下','理解界面过程']} size={78}/><PrincipleBadge/>
 </BlendSequence>
 <BlendSequence from={240} durationInFrames={90}><Shot id="A21" duration={90}/><Label text="持续观察"/></BlendSequence>
 <BlendSequence from={330} durationInFrames={90}><Shot id="B14" duration={90} position="50% 58%"/><Label text="细致维护"/></BlendSequence>
 <BlendSequence from={420} durationInFrames={120}><Shot id="A06" video trim={75} duration={120}/></BlendSequence>
 <BlendSequence from={540} durationInFrames={120}><SplitMontage left="A11" right="B11" text="把技术做实，把过程做细"/></BlendSequence>
 <BlendSequence from={660} durationInFrames={120}><Shot id="A28" duration={120} position="50% 53%"/><Label text="从建设，走向持续运行"/></BlendSequence>
 <Eyebrow duration={780} index="05" title="持续检验 · 长效守护"/>
 </AbsoluteFill>;
