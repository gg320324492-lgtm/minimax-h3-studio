import React from 'react';
import {AbsoluteFill,Img} from 'remotion';
import {asset,FONT,WHITE,MINT,GOLD,useTitleExit} from './Design';
export const CoverScene:React.FC=()=> {const exit=useTitleExit();return <AbsoluteFill style={{background:'#071e2a',fontFamily:FONT,overflow:'hidden'}}>
 <Img src={asset('B13.jpg')} style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'50% 54%',scale:1.035}}/>
 <AbsoluteFill style={{background:'linear-gradient(90deg,rgba(3,23,31,.9) 0%,rgba(3,23,31,.75) 33%,rgba(3,23,31,.3) 66%,rgba(3,23,31,.08) 100%)'}}/>
 <AbsoluteFill style={{background:'linear-gradient(0deg,rgba(3,23,31,.72),transparent 50%)'}}/>
 <AbsoluteFill style={{opacity:exit}}><div style={{position:'absolute',left:103,top:86,color:WHITE,fontSize:29,letterSpacing:5}}>天津大学 · 微纳米气泡课题组</div>
 <div style={{position:'absolute',left:103,top:234,display:'flex',alignItems:'center',gap:20,color:GOLD,fontSize:31,letterSpacing:5}}><span style={{width:55,height:2,background:GOLD}}/>黑臭水体治理现场实践</div>
 <div style={{position:'absolute',left:96,top:321,fontSize:143,fontWeight:700,letterSpacing:6,lineHeight:1.31,textShadow:'0 5px 25px rgba(0,0,0,.3)'}}>
 <div style={{color:WHITE}}>让水体</div><div style={{color:MINT}}>重新呼吸</div>
 </div>
 <div style={{position:'absolute',left:104,top:765,color:WHITE,fontSize:39,letterSpacing:4}}>微纳米气泡 <span style={{color:MINT,margin:'0 14px'}}>×</span> 生态浮岛</div>
 <div style={{position:'absolute',left:104,bottom:123,color:'#d3e7df',fontSize:27,letterSpacing:5}}>技术赋能 · 生态协同 · 持续守护</div>
 <div style={{position:'absolute',right:104,bottom:126,color:WHITE,fontSize:25,letterSpacing:4,borderBottom:'2px solid #97dfbd',paddingBottom:13}}>让科技扎根大地</div>
 </AbsoluteFill></AbsoluteFill>;};
