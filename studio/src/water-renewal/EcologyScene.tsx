import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence,interpolate,useCurrentFrame,Img} from 'remotion';
import {Shot,Label,Eyebrow,Statement,Portrait,PrincipleBadge,asset,FONT,MINT,WHITE,INK} from './Design';
const Roots:React.FC=()=>{
 const f=useCurrentFrame();return <AbsoluteFill style={{background:INK,fontFamily:FONT}}>
 <div style={{position:'absolute',left:1010,top:0,width:910,height:1080}}><Img src={asset('B15.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'43% 50%',scale:interpolate(f,[0,150],[1,1.04],{extrapolateRight:'clamp'})}}/></div>
 <AbsoluteFill style={{background:'linear-gradient(90deg,#071e2a 0%,#071e2a 39%,rgba(7,30,42,.74) 52%,transparent 73%)'}}/>
 <div style={{position:'absolute',top:190,left:110,color:WHITE,fontSize:61,fontWeight:700,letterSpacing:4}}>让生命参与修复</div>
 <svg viewBox="0 0 950 560" width="950" height="560" style={{position:'absolute',left:55,top:315}}>
 <path d="M45 202 Q250 190 465 202 T880 202" fill="none" stroke="#71bbb4" strokeWidth="2"/>
 <path d="M 185 185 L 770 185" stroke="#97dfbd" strokeWidth="16" strokeLinecap="round"/>
 {[235,360,490,620,740].map((x,i)=><g key={x}>
 <path d={`M${x} 175 Q${x-15} 120 ${x+12} 65`} fill="none" stroke={MINT} strokeWidth="4"/>
 <path d={`M${x} 120 Q${x-70} 50 ${x-15} 73 Q${x+22} 87 ${x} 120`} fill="#569f76"/>
 <path d={`M${x+5} 98 Q${x+63} 43 ${x+72} 64 Q${x+60} 98 ${x+5} 98`} fill="#9bcb84"/>
 {[0,1,2,3].map(k=><path key={k} d={`M${x} 197 Q${x-28+k*15} 260 ${x-42+k*29+Math.sin(f*.025+i)*5} ${318+k*16}`} fill="none" stroke="#c3d9b0" strokeWidth="1.8" opacity=".7"/>)}
 </g>)}
 {Array.from({length:30},(_,i)=><circle key={i} cx={195+(i*47)%590} cy={232+(i*71)%153+Math.sin(f*.03+i)*4} r={2+i%3} fill="#9ed4c4" opacity=".6"/>)}
 <text x="62" y="451" fill="#dceee6" fontSize="31" fontFamily={FONT}>根系延伸</text><text x="359" y="451" fill="#dceee6" fontSize="31" fontFamily={FONT}>微生物附着</text><text x="696" y="451" fill="#dceee6" fontSize="31" fontFamily={FONT}>协同净化</text>
 <path d="M250 443 H315 M610 443 H663" stroke="#89ccbd" strokeWidth="1.5"/>
 </svg>
 <PrincipleBadge label="生态作用示意"/>
 </AbsoluteFill>;
};
export const EcologyScene:React.FC=()=> <AbsoluteFill>
 <BlendSequence from={0} blend={28} durationInFrames={150}><Shot id="B13" duration={150} position="50% 59%"/><AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,27,34,.75),transparent)'}}/><Statement top={340} small="生态修复 · 新的接力" lines={['让更多生命','参与水体重建']} size={87}/></BlendSequence>
 <BlendSequence from={150} durationInFrames={105}><Shot id="B06" duration={105} position="50% 46%"/><Label text="材料运输"/></BlendSequence>
 <BlendSequence from={255} durationInFrames={75}><Shot id="B09" duration={75} position="50% 45%"/></BlendSequence>
 <BlendSequence from={330} durationInFrames={105}><Shot id="B05" video duration={105} fade={false}/><Label text="模块组装"/></BlendSequence>
 <BlendSequence from={435} durationInFrames={105}><Shot id="B07" duration={105} position="50% 60%"/></BlendSequence>
 <BlendSequence from={540} durationInFrames={90}><Shot id="B10" duration={90} position="50% 45%"/><Label text="植物准备"/></BlendSequence>
 <BlendSequence from={630} durationInFrames={90}><Shot id="B16" duration={90} position="50% 45%"/><Label text="协作入水"/></BlendSequence>
 <BlendSequence from={720} durationInFrames={90}><Shot id="B03" video trim={15} duration={90}/><Label text="栽植与布设"/></BlendSequence>
 <BlendSequence from={810} durationInFrames={150}><Roots/></BlendSequence>
 <BlendSequence from={960} durationInFrames={120}><Portrait id="B02" duration={120} trim={0} title="生态浮岛入水" detail="从一块单元，到一片生态空间"/></BlendSequence>
 <BlendSequence from={1080} durationInFrames={150}><Shot id="B12" duration={150} position="50% 58%"/><Label text="技术与生态 · 协同推进"/></BlendSequence>
 <BlendSequence from={1230} durationInFrames={150}><Shot id="B13" duration={150} position="50% 56%"/><Statement top={335} lines={['从设备运行','走向系统修复']} size={81}/></BlendSequence>
 <Eyebrow duration={1380} index="04" title="生态浮岛 · 生命的接力" green/>
 </AbsoluteFill>;
