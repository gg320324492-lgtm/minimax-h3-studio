import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia,renderStill,selectComposition} from '@remotion/renderer';
const dir=path.resolve('../water_renewal/07_edit');fs.mkdirSync(dir,{recursive:true});
const bundleDir=path.resolve('.remotion/water-renewal-bundle');
const mode=process.argv[2]??'still';
const url=await bundle({entryPoint:path.resolve('src/water-renewal/index.tsx'),outDir:bundleDir});
const composition=await selectComposition({serveUrl:url,id:mode==='cover'?'WaterCover':'WaterRenewalEdit'});
if(mode==='cover'){
 await renderStill({serveUrl:url,composition,frame:0,imageFormat:'jpeg',output:path.join(dir,'cover.jpg'),jpegQuality:96});
 console.log('Cover complete');
}else if(mode==='still'){
 const frames=(process.argv[3]??'180,465,840,1215,1560,1830,2330,2670,3020,3450,3700,4110,4410,4920,5260,5480,5730').split(',').map(Number);
 for(const frame of frames){
   await renderStill({serveUrl:url,composition,frame,imageFormat:'jpeg',output:path.join(dir,`qa_${frame}.jpg`),jpegQuality:92});
   console.log('frame',frame);
 }
}else{
 let last=0;
 await renderMedia({serveUrl:url,composition,codec:'h264',outputLocation:path.join(dir,'WaterRenewal_1080p.mp4'),crf:18,pixelFormat:'yuv420p',colorSpace:'bt709',imageFormat:'jpeg',jpegQuality:94,concurrency:16,offthreadVideoCacheSizeInBytes:2*1024*1024*1024,onProgress:({progress})=>{const p=Math.floor(progress*100);if(p>=last+5){last=p;console.log(`Render ${p}%`);}}});
 console.log('Render complete');
}
