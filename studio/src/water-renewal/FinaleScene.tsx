import {BlendSequence} from './Design';
import React from 'react';
import {AbsoluteFill,Sequence,Img,interpolate,useCurrentFrame} from 'remotion';
import {Shot,Statement,SplitMontage,asset,FONT,WHITE,MINT,GOLD,INK} from './Design';
const EndCard:React.FC=()=>{
 const f=useCurrentFrame();return <AbsoluteFill style={{background:INK,fontFamily:FONT}}>
 <Img src={asset('B13.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'50% 54%',opacity:.19,scale:interpolate(f,[0,360],[1.08,1.02],{extrapolateRight:'clamp'})}}/>
 <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,24,32,.62),rgba(3,24,32,.5))'}}/>
 <div style={{position:'absolute',left:0,right:0,top:207,textAlign:'center',opacity:interpolate(f,[0,27],[0,1],{extrapolateRight:'clamp'})}}>
 <div style={{fontSize:29,color:GOLD,letterSpacing:8,marginBottom:33}}>让科技扎根大地</div>
 <div style={{fontSize:100,fontWeight:700,color:WHITE,letterSpacing:7,lineHeight:1.25}}>让水体重新呼吸</div>
 <div style={{margin:'42px auto 34px',width:98,height:2,background:MINT}}/>
 <div style={{fontSize:43,color:MINT,letterSpacing:5,lineHeight:1.55}}>让我们一起</div>
 <div style={{fontSize:38,color:MINT,letterSpacing:3,lineHeight:1.6}}>共建人与自然和谐共生的美好家园</div>
 </div>
 <div style={{position:'absolute',top:765,left:0,right:0,textAlign:'center',color:WHITE,opacity:interpolate(f,[65,105],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>
 <div style={{fontSize:33,fontWeight:600,letterSpacing:4}}>天津大学 微纳米气泡课题组</div>
 <div style={{fontSize:24,letterSpacing:2,marginTop:16,color:'#c0d6d1'}}>Micro & Nano Bubble Technology Lab · mnb-lab.cn</div>
 </div>
 </AbsoluteFill>;
};
export const FinaleScene:React.FC=()=> <AbsoluteFill>
 <BlendSequence from={0} blend={28} durationInFrames={64}><Shot id="A08" video trim={630} duration={64}/><Statement top={350} small="改变 · 始于行动" lines={['一颗气泡']} size={112}/></BlendSequence>
 <BlendSequence from={64} durationInFrames={45}><Shot id="B13" duration={45} position="50% 75%" zoom={1.04}/><AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,24,30,.62),transparent)'}}/><Statement top={350} lines={['一株绿植']} size={112}/></BlendSequence>
 <BlendSequence from={109} durationInFrames={131}><SplitMontage left="A15" right="B16" text="一群躬身实干的人"/></BlendSequence>
 <BlendSequence from={240} durationInFrames={150}><Shot id="B11" duration={150} position="50% 40%"/><Statement top={350} small="改变 · 始于行动" lines={['把期待','变成具体的行动']} size={83}/></BlendSequence>
 <BlendSequence from={390} durationInFrames={150}><Shot id="B11" duration={150} position="50% 38%"/><Statement top={340} lines={['守护一条河','也是守护一方家园']} size={82}/></BlendSequence>
 <BlendSequence from={540} durationInFrames={120}><Shot id="A27" duration={120}/></BlendSequence>
 <BlendSequence from={660} durationInFrames={180}><Shot id="B13" duration={180} position="50% 54%"/><AbsoluteFill style={{background:'rgba(3,27,34,.36)'}}/><Statement top={340} small="向着水清岸绿的愿景" lines={['让水体重新呼吸','让科技扎根大地']} size={88}/></BlendSequence>
 <BlendSequence from={840} durationInFrames={360}><EndCard/></BlendSequence>
 </AbsoluteFill>;
