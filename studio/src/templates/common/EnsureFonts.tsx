import React, {useEffect} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';

// 自托管中文字体：headless Chrome 对系统字体的可见性不保证跨机一致，
// 渲染关键字体一律走 public/fonts/ 自托管（ttf/woff2；.ttc 需先转换）。
const loaded: string[] = [];

export const registerFont = (family: string, file: string): number => {
  const handle = delayRender(`Loading font ${family}`);
  const font = new FontFace(family, `url(${staticFile(file)})`);
  font
    .load()
    .then((loaded_) => {
      document.fonts.add(loaded_);
      loaded.push(family);
      continueRender(handle);
    })
    .catch((err) => {
      continueRender(handle);
      throw err;
    });
  return handle;
};

export const EnsureFonts: React.FC<{children: React.ReactNode}> = ({children}) => {
  useEffect(() => {
    registerFont('SimHeiLocal', 'fonts/simhei.ttf');
  }, []);
  return <>{children}</>;
};
