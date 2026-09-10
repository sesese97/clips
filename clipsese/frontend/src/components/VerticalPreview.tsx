import { useEffect, useRef } from 'react';
import type { Crop, Layout, Media } from '../types';
import { fileUrl } from '../lib/api';

type Props={projectId:string;videoUrl:string;layout:Layout;crops:Record<string,Crop>;media?:Media;currentTime:number};

export default function VerticalPreview({projectId,videoUrl,layout,crops,media,currentTime}:Props){
  const canvas=useRef<HTMLCanvasElement>(null); const source=useRef<HTMLVideoElement>(null); const mediaVideo=useRef<HTMLVideoElement>(null); const mediaImg=useRef<HTMLImageElement>(null);
  useEffect(()=>{ if(source.current && Math.abs(source.current.currentTime-currentTime)>.35) source.current.currentTime=currentTime; },[currentTime]);
  useEffect(()=>{
    let raf=0;
    const drawCrop=(ctx:CanvasRenderingContext2D,el:CanvasImageSource,c:Crop,dx:number,dy:number,dw:number,dh:number,sw:number,sh:number)=>{
      ctx.drawImage(el,c.x*sw,c.y*sh,c.w*sw,c.h*sh,dx,dy,dw,dh);
    };
    const loop=()=>{
      const cv=canvas.current, v=source.current; if(!cv||!v||!v.videoWidth){raf=requestAnimationFrame(loop);return}
      const ctx=cv.getContext('2d')!; ctx.fillStyle='#05070b';ctx.fillRect(0,0,360,640);
      if(layout==='one_media') drawCrop(ctx,v,crops.camera1,0,0,360,240,v.videoWidth,v.videoHeight);
      if(layout==='two_cameras'){
        drawCrop(ctx,v,crops.camera1,0,0,360,320,v.videoWidth,v.videoHeight);
        drawCrop(ctx,v,crops.camera2,0,320,360,320,v.videoWidth,v.videoHeight);
      }
      if(layout==='two_media'){
        drawCrop(ctx,v,crops.camera1,0,0,180,240,v.videoWidth,v.videoHeight);
        drawCrop(ctx,v,crops.camera2,180,0,180,240,v.videoWidth,v.videoHeight);
      }
      if(layout!=='two_cameras'){
        const y=240,h=400;
        const mv=mediaVideo.current, mi=mediaImg.current;
        if(media?.type==='video' && mv?.videoWidth) ctx.drawImage(mv,0,0,mv.videoWidth,mv.videoHeight,0,y,360,h);
        else if(media?.type==='image' && mi?.naturalWidth) ctx.drawImage(mi,0,0,mi.naturalWidth,mi.naturalHeight,0,y,360,h);
        else drawCrop(ctx,v,crops.content,0,y,360,h,v.videoWidth,v.videoHeight);
      }
      raf=requestAnimationFrame(loop);
    };
    raf=requestAnimationFrame(loop); return()=>cancelAnimationFrame(raf);
  },[layout,crops,media,videoUrl]);
  const murl=media?fileUrl(projectId,media.file):'';
  return <div className="vertical-preview">
    <canvas ref={canvas} width={360} height={640}/>
    <video ref={source} src={videoUrl} muted playsInline onLoadedMetadata={()=>{if(source.current) source.current.currentTime=currentTime}} style={{display:'none'}}/>
    {media?.type==='video'&&<video ref={mediaVideo} src={murl} muted autoPlay loop playsInline style={{display:'none'}}/>}
    {media?.type==='image'&&<img ref={mediaImg} src={murl} style={{display:'none'}}/>}
  </div>
}
