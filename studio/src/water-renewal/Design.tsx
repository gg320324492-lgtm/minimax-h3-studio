import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, Freeze, interpolate, useCurrentFrame, Easing, staticFile} from 'remotion';
import {Video} from '@remotion/media';

export const FONT='"Microsoft YaHei", "SimHeiLocal", sans-serif';
export const INK='#071e2a', WHITE='#f2f8f5', MINT='#97dfbd', GOLD='#eed795';
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
export const asset=(name:string)=>staticFile(`jobs/water-renewal/${name}`);
const PictureDuration=React.createContext(100000);
export const useTitleExit=()=>{
 const f=useCurrentFrame(),d=React.useContext(PictureDuration);
 return interpolate(f,[d-Math.min(18,d*.22),d-1],[1,0],clamp);
};

const BlendContent:React.FC<{duration:number;fadeIn:boolean;blend:number;children:React.ReactNode}>=({duration,fadeIn,blend,children})=>{
 const f=useCurrentFrame();return <AbsoluteFill style={{opacity:fadeIn?interpolate(f,[0,blend],[0,1],{...clamp,easing:Easing.inOut(Easing.sin)}):1}}>
 <PictureDuration.Provider value={duration}>{f>=duration?<Freeze frame={duration-1}>{children}</Freeze>:children}</PictureDuration.Provider>
 </AbsoluteFill>;
};
// Overlap only the picture tail; authored starts and narration remain absolute.
export const BlendSequence:React.FC<{from:number;durationInFrames:number;fadeIn?:boolean;blend?:number;children:React.ReactNode}>=({from,durationInFrames,fadeIn=true,blend=21,children})=>
 <Sequence from={from} durationInFrames={durationInFrames+30}>
 <BlendContent duration={durationInFrames} fadeIn={fadeIn} blend={blend}>{children}</BlendContent>
 </Sequence>;

export const Shot:React.FC<{id:string;duration:number;video?:boolean;trim?:number;fade?:boolean;position?:string;zoom?:number}>=({id,duration,video=false,trim=0,fade=false,position='50% 50%',zoom=1.05})=>{
  const f=useCurrentFrame();
  return <AbsoluteFill style={{overflow:'hidden',opacity:fade?interpolate(f,[0,15],[0,1],clamp):1}}>
    {video?<Video src={asset(id+'.mp4')} trimBefore={trim} muted style={{width:'100%',height:'100%'}} objectFit="cover"/>:
      <Img src={asset(id+'.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:position,scale:interpolate(f,[0,duration],[1,zoom],clamp)}}/>}
    <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(1,19,25,.12) 0%,transparent 48%,rgba(2,16,22,.55) 100%)'}}/>
  </AbsoluteFill>;
};

export const Eyebrow:React.FC<{index:string;title:string;green?:boolean;duration?:number}>=({index,title,green=false,duration=100000})=>{
 const f=useCurrentFrame();return <div style={{position:'absolute',top:70,left:94,display:'flex',alignItems:'center',gap:20,fontFamily:FONT,color:WHITE,opacity:interpolate(f,[0,21],[0,1],clamp)*interpolate(f,[duration-24,duration],[1,0],clamp),textShadow:'0 2px 14px #071e2a'}}>
 <span style={{fontSize:26,color:green?MINT:GOLD,letterSpacing:2}}>{index}</span><div style={{height:1,width:54,background:green?MINT:GOLD}}/><span style={{fontSize:29,fontWeight:500,letterSpacing:4}}>{title}</span></div>;
};

export const Statement:React.FC<{top?:number;small?:string;lines:string[];accent?:string;align?:'left'|'center';size?:number}>=({top=360,small,lines,accent=MINT,align='left',size=86})=>{
 const f=useCurrentFrame(),exit=useTitleExit();return <div style={{position:'absolute',top,left:96,right:96,textAlign:align,fontFamily:FONT,color:WHITE,opacity:exit,textShadow:'0 4px 24px rgba(0,0,0,.6)'}}>
 {small&&<div style={{fontSize:28,letterSpacing:6,color:accent,marginBottom:26,opacity:interpolate(f,[0,18],[0,1],clamp)}}>{small}</div>}
 {lines.map((l,i)=><div key={l} style={{fontSize:size,fontWeight:700,lineHeight:1.38,letterSpacing:5,color:i===lines.length-1?accent:WHITE,opacity:interpolate(f,[i*9,i*9+24],[0,1],clamp),translate:`0px ${interpolate(f,[i*9,i*9+28],[30,0],{...clamp,easing:Easing.out(Easing.cubic)})}px`}}>{l}</div>)}
 </div>;
};

export const Label:React.FC<{text:string;sub?:string;right?:boolean}>=({text,sub,right=false})=>{
 const f=useCurrentFrame(),exit=useTitleExit();return <div style={{position:'absolute',bottom:192,[right?'right':'left']:96,fontFamily:FONT,color:WHITE,padding:'20px 30px',borderLeft:`3px solid ${MINT}`,background:'linear-gradient(90deg,rgba(3,28,36,.88),rgba(3,28,36,.25))',opacity:interpolate(f,[0,15],[0,1],clamp)*exit,translate:`${interpolate(f,[0,24],[right?22:-22,0],clamp)}px 0px`}}><div style={{fontSize:37,fontWeight:600,letterSpacing:2}}>{text}</div>{sub&&<div style={{fontSize:23,color:'#cedfdc',marginTop:10,letterSpacing:2}}>{sub}</div>}</div>;
};

export const Portrait:React.FC<{id:string;duration:number;trim?:number;title:string;detail:string;photo?:string}>=({id,duration,trim=0,title,detail,photo='B13'})=>{
 const f=useCurrentFrame(),exit=useTitleExit();return <AbsoluteFill style={{background:INK,fontFamily:FONT}}>
 <Img src={asset(photo+'.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',filter:'blur(20px) brightness(.28)',scale:1.12}}/>
 <div style={{position:'absolute',left:1140,top:60,width:550,height:978,overflow:'hidden',border:'1px solid rgba(151,223,189,.3)',boxShadow:'0 18px 65px #031119',opacity:interpolate(f,[0,15],[0,1],clamp)}}>
 <Video src={asset(id+'.mp4')} trimBefore={trim} muted style={{width:'100%',height:'100%'}} objectFit="cover"/>
 </div>
 <div style={{position:'absolute',left:120,top:355,width:800,opacity:exit}}><div style={{width:75,height:3,background:MINT,marginBottom:40}}/>
 <div style={{fontSize:76,fontWeight:700,color:WHITE,lineHeight:1.5,letterSpacing:5}}>{title}</div>
 <div style={{fontSize:32,color:MINT,marginTop:28,lineHeight:1.8,letterSpacing:3}}>{detail}</div></div>
 </AbsoluteFill>;
};

export const PrincipleBadge:React.FC<{label?:string}>=({label='原理示意 · 非现场实拍'})=><div style={{position:'absolute',top:77,right:95,color:'#d7e8e2',fontSize:24,fontFamily:FONT,letterSpacing:2,padding:'10px 18px',border:'1px solid rgba(215,232,226,.4)',background:'rgba(3,20,27,.65)'}}>{label}</div>;

export const SplitMontage:React.FC<{left:string;right:string;text:string}>=({left,right,text})=>{
 const f=useCurrentFrame(),exit=useTitleExit();return <AbsoluteFill style={{background:INK,fontFamily:FONT}}>
 <div style={{position:'absolute',left:0,top:0,width:955,height:1080,overflow:'hidden'}}><Img src={asset(left+'.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',scale:interpolate(f,[0,150],[1.01,1.07],clamp)}}/></div>
 <div style={{position:'absolute',left:965,top:0,width:955,height:1080,overflow:'hidden'}}><Img src={asset(right+'.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',scale:interpolate(f,[0,150],[1.07,1.01],clamp)}}/></div>
 <AbsoluteFill style={{background:'linear-gradient(0deg,rgba(2,18,25,.8),transparent 70%)'}}/>
 <div style={{position:'absolute',left:96,bottom:230,color:WHITE,fontSize:70,fontWeight:700,letterSpacing:8,opacity:exit,textShadow:'0 5px 18px #071e2a'}}>{text}</div></AbsoluteFill>;
};
