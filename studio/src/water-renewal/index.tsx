import React from 'react';
import {Composition,Folder,registerRoot} from 'remotion';
import {Film} from './Film';
import {PacedPreview} from './PacedPreview';
import {OpeningScene} from './OpeningScene';
import {FieldScene} from './FieldScene';
import {BubbleScene} from './BubbleScene';
import {EcologyScene} from './EcologyScene';
import {ValidationScene} from './ValidationScene';
import {FinaleScene} from './FinaleScene';
import {CoverScene} from './CoverScene';
import {EnsureFonts} from '../templates/common/EnsureFonts';
const Root:React.FC=()=> <>
 <Composition id="WaterRenewal" component={PacedPreview} width={1920} height={1080} fps={30} durationInFrames={5500}/>
 <Composition id="WaterRenewalEdit" component={Film} width={1920} height={1080} fps={30} durationInFrames={5940}/>
 <Composition id="WaterCover" component={CoverScene} width={1920} height={1080} fps={30} durationInFrames={1}/>
 <Folder name="WaterRenewal-Scenes">
 <Composition id="Opening" component={OpeningScene} width={1920} height={1080} fps={30} durationInFrames={720}/>
 <Composition id="Field" component={FieldScene} width={1920} height={1080} fps={30} durationInFrames={750}/>
 <Composition id="Bubbles" component={BubbleScene} width={1920} height={1080} fps={30} durationInFrames={1110}/>
 <Composition id="Ecology" component={EcologyScene} width={1920} height={1080} fps={30} durationInFrames={1380}/>
 <Composition id="Validation" component={ValidationScene} width={1920} height={1080} fps={30} durationInFrames={780}/>
 <Composition id="Finale" component={FinaleScene} width={1920} height={1080} fps={30} durationInFrames={1200}/>
 </Folder>
 </>;
registerRoot(Root);
