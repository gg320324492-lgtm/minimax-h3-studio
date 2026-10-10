import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence,OffthreadVideo,interpolate,useCurrentFrame} from 'remotion';
import {Shot,Eyebrow,Label,Statement,PrincipleBadge,asset,FONT,MINT,WHITE} from './Design';
const Mechanism:React.FC=()=>{
 const f=useCurrentFrame();return <AbsoluteFill style={{background:'#071d28',fontFamily:FONT}}>
 <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{position:'absolute'}}>
 <defs><radialGradient id="bubble"><stop stopColor="#effff9" stopOpacity=".06"/><stop offset=".77" stopColor="#67cebe" stopOpacity=".1"/><stop offset="1" stopColor="#b0f4de" stopOpacity=".85"/></radialGradient></defs>
 {Array.from({length:32},(_,i)=>{const x=950+(i*137)%780;const y=920-((f*1.8+i*57)%770);const r=7+(i%5)*8;return <circle key={i} cx={x} cy={y} r={r} fill="url(#bubble)"/>;})}
 <path d="M 100 730 Q 500 680 900 725 T 1780 710" fill="none" stroke="#6fcbb9" strokeWidth="2" opacity=".4"/>
 <path d="M 100 751 Q 500 704 900 748 T 1780 733" fill="none" stroke="#6fcbb9" opacity=".15"/>
 </svg>
 <Statement top={330} small="微小尺度 · 持续作用" lines={['强化气液传质','连接气与水']} size={83}/>
 <PrincipleBadge/>
 </AbsoluteFill>;
};
export const BubbleScene:React.FC=()=> <AbsoluteFill>
 <BlendSequence from={0} blend={28} durationInFrames={240}>
 <OffthreadVideo src={asset('micro.mp4')} muted style={{width:'100%',height:'100%',objectFit:'cover'}}/>
 <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(0,20,28,.75),rgba(0,20,28,.05) 85%)'}}/>
 <Statement top={342} small="从微观尺度出发" lines={['一颗气泡','一条技术路径']} size={86}/><PrincipleBadge/>
 </BlendSequence>
 <BlendSequence from={240} durationInFrames={150}><Mechanism/></BlendSequence>
 <BlendSequence from={390} durationInFrames={105}><Shot id="A07" video duration={105}/><Label text="清理漂浮物"/></BlendSequence>
 <BlendSequence from={495} durationInFrames={105}><Shot id="A15" duration={105}/></BlendSequence>
 <BlendSequence from={600} durationInFrames={150}><Shot id="A05" video trim={60} duration={150}/><Label text="输送管线布设"/></BlendSequence>
 <BlendSequence from={750} durationInFrames={180}><Shot id="A08" video trim={600} duration={180}/><Label text="现场运行" sub="气泡云在水下持续扩散"/></BlendSequence>
 <BlendSequence from={930} durationInFrames={180}><Shot id="A08" video trim={1020} duration={180}/><Statement top={360} lines={['让技术','接受现场检验']} size={80}/></BlendSequence>
 <Eyebrow duration={1110} index="03" title="气泡技术 · 工程实践"/>
 </AbsoluteFill>;
