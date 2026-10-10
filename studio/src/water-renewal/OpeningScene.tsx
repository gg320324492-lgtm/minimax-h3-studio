import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence,interpolate,useCurrentFrame} from 'remotion';
import {Shot,Statement,Eyebrow,Label,FONT,MINT,WHITE} from './Design';
import {CoverScene} from './CoverScene';
export const OpeningScene:React.FC=()=>{
const f=useCurrentFrame();return <AbsoluteFill>
 <BlendSequence from={0} durationInFrames={90} fadeIn={false}><CoverScene/></BlendSequence>
 <BlendSequence from={90} durationInFrames={150}><Shot id="A03" video duration={150} fade={false}/></BlendSequence>
 <BlendSequence from={240} durationInFrames={120}><Shot id="A27" duration={120} position="50% 55%"/></BlendSequence>
 <BlendSequence from={360} durationInFrames={150}><Shot id="A04" video trim={15} duration={150}/></BlendSequence>
 <BlendSequence from={510} durationInFrames={210}><Shot id="A20" duration={210}/></BlendSequence>
 <Sequence from={90} durationInFrames={270}><AbsoluteFill style={{opacity:interpolate(f,[90,111,336,360],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>
 <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,24,33,.64),rgba(3,24,33,.15) 70%)'}}/>
 <Statement top={315} small="黑臭水体治理 · 现场实践" lines={['让水体','重新呼吸']} size={116}/>
 <div style={{position:'absolute',left:103,top:722,fontFamily:FONT,fontSize:34,letterSpacing:5,color:WHITE,opacity:interpolate(f,[35,70],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>微纳米气泡 × 生态浮岛</div>
 <div style={{position:'absolute',top:82,left:103,fontFamily:FONT,fontSize:24,letterSpacing:4,color:'#d4e8e2'}}>天津大学 · 微纳米气泡课题组</div>
 </AbsoluteFill></Sequence>
 <Sequence from={360} durationInFrames={360}><AbsoluteFill style={{opacity:interpolate(f,[360,388,696,720],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}><Eyebrow duration={360} index="01" title="直面问题"/><Statement top={355} lines={['看见问题','才能回应期待']} size={83}/></AbsoluteFill></Sequence>
 </AbsoluteFill>;
};
