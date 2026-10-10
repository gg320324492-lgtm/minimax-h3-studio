import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Video} from '@remotion/media';
import {asset} from './Design';

// Preview the verified delivery, including pitch-preserving audio retiming.
export const PacedPreview:React.FC=()=> <AbsoluteFill style={{background:'#071e2a'}}>
  <Video src={asset('paced_108.mp4')} style={{width:'100%',height:'100%'}} objectFit="contain"/>
</AbsoluteFill>;
