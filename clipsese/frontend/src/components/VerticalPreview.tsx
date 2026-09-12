import { useEffect, useRef } from 'react';
import type { Crop, Layout, Media, MediaTransform } from '../types';
import { fileUrl } from '../lib/api';

type Props={projectId:string;videoUrl:string;layout:Layout;crops:Record<string,Crop>;media?:Media;mediaTransform:MediaTransform;currentTime:number;playing?:boolean};

const hiddenVideoStyle:React.CSSProperties={position:'fixed',left:-9999,top:0,width:2,height:2,opacity:.001,pointerEvents:'none'};

export default function VerticalPreview({projectId,videoUrl,layout,crops,media,mediaTransform,currentTime,playing=false}:Props){
  const canvas=useRef<HTMLCanvasElement>(null); const source=useRef<HTMLVideoElement>(null); const mediaVideo=useRef<HTMLVideoElement>(null); const mediaImg=useRef<HTMLImageElement>(null);

  useEffect(()=>{
    const v=source.current;
    if(!v || !Number.isFinite(currentTime))return;
    const tolerance=playing?.85:.18;
    if(Math.abs(v.currentTime-currentTime)>tolerance){
      try{v.currentTime=currentTime}catch{}
    }
  },[currentTime,playing,videoUrl]);

  useEffect(()=>{
    const v=source.current;
    if(!v)return;
    if(playing){
      v.play().catch(()=>{});
    }else{
      v.pause();
    }
  },[playing,videoUrl]);

  useEffect(()=>{
    let raf=0;
    const drawCrop=(ctx:CanvasRenderingContext2D,el:CanvasImageSource,c:Crop,dx:number,dy:number,dw:number,dh:number,sw:number,sh:number)=>{
      let sx=c.x*sw,sy=c.y*sh,cw=c.w*sw,ch=c.h*sh;
      const srcAspect=cw/ch,dstAspect=dw/dh;
      if(srcAspect>dstAspect){const nw=ch*dstAspect;sx+=(cw-nw)/2;cw=nw}
      else if(srcAspect<dstAspect){const nh=cw/dstAspect;sy+=(ch-nh)/2;ch=nh}
      ctx.drawImage(el,sx,sy,cw,ch,dx,dy,dw,dh);
    };
    const drawMedia=(ctx:CanvasRenderingContext2D,el:CanvasImageSource,sw:number,sh:number,dx:number,dy:number,dw:number,dh:number)=>{
      const base=mediaTransform.fit==='cover'?Math.max(dw/sw,dh/sh):Math.min(dw/sw,dh/sh);
      const scale=base*mediaTransform.zoom;
      const rw=sw*scale,rh=sh*scale;
      const x=dx+(dw-rw)*((mediaTransform.x+1)/2);
      const y=dy+(dh-rh)*((mediaTransform.y+1)/2);
      ctx.save();ctx.beginPath();ctx.rect(dx,dy,dw,dh);ctx.clip();ctx.fillStyle='#000';ctx.fillRect(dx,dy,dw,dh);ctx.drawImage(el,x,y,rw,rh);ctx.restore();
    };
    const loop=()=>{
      const cv=canvas.current, v=source.current;
      if(!cv){raf=requestAnimationFrame(loop);return}
      const ctx=cv.getContext('2d')!;
      ctx.fillStyle='#05070b';ctx.fillRect(0,0,360,640);
      if(!v || !v.videoWidth || v.readyState<2){raf=requestAnimationFrame(loop);return}

      try{
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
          if(media?.type==='video' && mv?.videoWidth && mv.readyState>=2) drawMedia(ctx,mv,mv.videoWidth,mv.videoHeight,0,y,360,h);
          else if(media?.type==='image' && mi?.naturalWidth) drawMedia(ctx,mi,mi.naturalWidth,mi.naturalHeight,0,y,360,h);
          else drawCrop(ctx,v,crops.content,0,y,360,h,v.videoWidth,v.videoHeight);
        }
      }catch{}
      raf=requestAnimationFrame(loop);
    };
    raf=requestAnimationFrame(loop); return()=>cancelAnimationFrame(raf);
  },[layout,crops,media,mediaTransform,videoUrl]);

  const murl=media?fileUrl(projectId,media.file):'';
  return <div className="vertical-preview">
    <canvas ref={canvas} width={360} height={640}/>
    <video
      ref={source}
      src={videoUrl}
      muted
      playsInline
      preload="auto"
      onLoadedMetadata={()=>{const v=source.current;if(v){try{v.currentTime=currentTime}catch{}}}}
      onLoadedData={()=>{const v=source.current;if(v&&playing)v.play().catch(()=>{})}}
      style={hiddenVideoStyle}
    />
    {media?.type==='video'&&<video ref={mediaVideo} src={murl} muted autoPlay loop playsInline preload="auto" style={hiddenVideoStyle}/>} 
    {media?.type==='image'&&<img ref={mediaImg} src={murl} alt="" style={{position:'fixed',left:-9999,width:2,height:2,opacity:.001}}/>}
  </div>
}
