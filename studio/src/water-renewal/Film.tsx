import React from 'react';
import {AbsoluteFill,Sequence,useCurrentFrame,interpolate,Audio} from 'remotion';
import type {Caption} from '@remotion/captions';
import {EnsureFonts} from '../templates/common/EnsureFonts';
import {OpeningScene} from './OpeningScene';
import {FieldScene} from './FieldScene';
import {BubbleScene} from './BubbleScene';
import {EcologyScene} from './EcologyScene';
import {ValidationScene} from './ValidationScene';
import {FinaleScene} from './FinaleScene';
import {FONT,asset,MINT} from './Design';
import captionsData from './captions.json';

const captions=captionsData as Caption[];
const Captions:React.FC=()=>{
 const f=useCurrentFrame(),ms=f/30*1000;const c=captions.find(x=>ms>=x.startMs&&ms<x.endMs);
 if(!c)return null;
 const local=f-c.startMs/1000*30;
 return <div style={{position:'absolute',bottom:78,left:100,right:100,display:'flex',justifyContent:'center',fontFamily:FONT}}>
 <div style={{fontSize:43,fontWeight:500,color:'#fff',letterSpacing:2,lineHeight:1.4,padding:'12px 29px 14px',background:'rgba(2,17,24,.79)',borderBottom:'2px solid rgba(151,223,189,.55)',borderRadius:3,textShadow:'0 2px 5px #000',opacity:interpolate(local,[0,4],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>{c.text.split(/(微纳米气泡|生态浮岛|美好家园|持续行动|气液传质|根系|现场检验|系统修复|科技扎根大地)/g).map((part,i)=>i%2?<span key={i} style={{color:MINT,fontWeight:700}}>{part}</span>:part)}</div>
 </div>;
};
export const Film:React.FC=()=> <EnsureFonts><AbsoluteFill style={{background:'#071e2a'}}>
 <Sequence from={0} durationInFrames={750} name="序章 · 一条河的期待"><OpeningScene/></Sequence>
 <Sequence from={720} durationInFrames={780} name="现场 · 从问题到方案"><FieldScene/></Sequence>
 <Sequence from={1470} durationInFrames={1140} name="技术 · 气泡的力量"><BubbleScene/></Sequence>
 <Sequence from={2580} durationInFrames={1410} name="生态 · 生命的接力"><EcologyScene/></Sequence>
 <Sequence from={3960} durationInFrames={810} name="实践 · 持续检验"><ValidationScene/></Sequence>
 <Sequence from={4740} durationInFrames={1200} name="尾章 · 向着美好家园"><FinaleScene/></Sequence>
 <Captions/>
 <Audio key="call-to-action-20261010" src={asset('master.wav')+'?revision=call-to-action-20261010'}/>
 </AbsoluteFill></EnsureFonts>;
