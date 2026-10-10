import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence} from 'remotion';
import {Shot,Label,Eyebrow} from './Design';
export const FieldScene:React.FC=()=> <AbsoluteFill>
 <BlendSequence from={0} blend={28} durationInFrames={150}><Shot id="A09" duration={150} position="50% 45%"/><Label text="共同研判" sub="让方案回应现场问题"/></BlendSequence>
 <BlendSequence from={150} durationInFrames={120}><Shot id="A10" duration={120} position="50% 42%"/></BlendSequence>
 <BlendSequence from={270} durationInFrames={120}><Shot id="A11" duration={120} position="50% 54%"/><Label text="现场调试" sub="让研究落到具体行动"/></BlendSequence>
 <BlendSequence from={390} durationInFrames={120}><Shot id="A19" duration={120} position="50% 55%"/><Label text="臭氧微纳米气泡一体机"/></BlendSequence>
 <BlendSequence from={510} durationInFrames={120}><Shot id="A01" video trim={150} duration={120}/></BlendSequence>
 <BlendSequence from={630} durationInFrames={120}><Shot id="A13" duration={120}/><Label text="曝气单元布设"/></BlendSequence>
 <Eyebrow duration={750} index="02" title="把技术带到河道"/>
 </AbsoluteFill>;
