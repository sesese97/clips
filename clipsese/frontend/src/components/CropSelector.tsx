import { useEffect, useRef, useState } from 'react';
import type { Crop } from '../types';

type Props = {
  videoUrl: string;
  currentTime: number;
  crops: Record<string, Crop>;
  active: string;
  onActive: (name:string)=>void;
  onCrop: (name:string,crop:Crop)=>void;
  onTimeChange?: (time:number)=>void;
  onPlayingChange?: (playing:boolean)=>void;
};

type Gesture =
  | {type:'draw';name:string;start:{x:number;y:number}}
  | {type:'move'|'resize';name:string;start:{x:number;y:number};original:Crop}
  | null;

const labels: Record<string,string> = {camera1:'Cámara 1',camera2:'Cámara 2',content:'Contenido'};
const cropKeys=['camera1','camera2','content'];

export default function CropSelector({videoUrl,currentTime,crops,active,onActive,onCrop,onTimeChange,onPlayingChange}:Props){
  const wrap=useRef<HTMLDivElement>(null);
  const video=useRef<HTMLVideoElement>(null);
  const [gesture,setGesture]=useState<Gesture>(null);

  useEffect(()=>{
    const v=video.current;
    if(!v || !Number.isFinite(currentTime))return;
    if(Math.abs(v.currentTime-currentTime)>.65){
      try{v.currentTime=currentTime}catch{}
    }
  },[currentTime,videoUrl]);

  function point(e: React.PointerEvent){
    const r=wrap.current!.getBoundingClientRect();
    return {x:Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))};
  }
  function backgroundDown(e:React.PointerEvent){
    if((e.target as HTMLElement).closest('.crop-box'))return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setGesture({type:'draw',name:active,start:point(e)});
  }
  function boxDown(e:React.PointerEvent<HTMLElement>,name:string,type:'move'|'resize'){
    e.preventDefault();
    e.stopPropagation();
    onActive(name);
    e.currentTarget.setPointerCapture(e.pointerId);
    setGesture({type,name,start:point(e),original:{...crops[name]}});
  }
  function move(e:React.PointerEvent){
    if(!gesture)return;
    if(gesture.type!=='draw'){
      e.preventDefault();
      e.stopPropagation();
    }
    const p=point(e);
    if(gesture.type==='draw'){
      const x=Math.min(gesture.start.x,p.x), y=Math.min(gesture.start.y,p.y);
      const w=Math.max(.03,Math.abs(p.x-gesture.start.x)), h=Math.max(.03,Math.abs(p.y-gesture.start.y));
      onCrop(gesture.name,{x,y,w:Math.min(w,1-x),h:Math.min(h,1-y)});
      return;
    }
    const dx=p.x-gesture.start.x,dy=p.y-gesture.start.y;
    const o=gesture.original;
    if(gesture.type==='move'){
      const x=Math.max(0,Math.min(1-o.w,o.x+dx));
      const y=Math.max(0,Math.min(1-o.h,o.y+dy));
      onCrop(gesture.name,{...o,x,y});
    }else{
      const w=Math.max(.03,Math.min(1-o.x,o.w+dx));
      const h=Math.max(.03,Math.min(1-o.y,o.h+dy));
      onCrop(gesture.name,{...o,w,h});
    }
  }
  function up(){setGesture(null)}
  function sync(){
    const v=video.current;
    if(!v)return;
    if(Math.abs(v.currentTime-currentTime)>.4){
      try{v.currentTime=currentTime}catch{}
    }
    onTimeChange?.(v.currentTime);
  }

  return <div>
    <div className="crop-tabs">{cropKeys.filter(k=>crops[k]).map(k=><button key={k} className={active===k?'active':''} onClick={()=>onActive(k)}>{labels[k]}</button>)}</div>
    <div
      className="video-crop-wrap"
      ref={wrap}
      onPointerDown={backgroundDown}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onDragStart={e=>e.preventDefault()}
      style={{userSelect:'none',WebkitUserSelect:'none'}}
    >
      <video
        ref={video}
        src={videoUrl}
        controls
        preload="auto"
        playsInline
        draggable={false}
        onDragStart={e=>e.preventDefault()}
        onLoadedMetadata={sync}
        onSeeked={()=>{const v=video.current;if(v)onTimeChange?.(v.currentTime)}}
        onTimeUpdate={()=>{const v=video.current;if(v)onTimeChange?.(v.currentTime)}}
        onPlay={()=>onPlayingChange?.(true)}
        onPause={()=>onPlayingChange?.(false)}
        onEnded={()=>onPlayingChange?.(false)}
      />
      {cropKeys.filter(k=>crops[k]).map(k=>{
        const c=crops[k];
        return <div
          key={k}
          data-crop={k}
          draggable={false}
          className={`crop-box ${active===k?'selected':''}`}
          onPointerDown={e=>boxDown(e,k,'move')}
          onDragStart={e=>e.preventDefault()}
          style={{left:`${c.x*100}%`,top:`${c.y*100}%`,width:`${c.w*100}%`,height:`${c.h*100}%`}}
        >
          <span>{labels[k]}</span>
          {active===k&&<i className="crop-resize" draggable={false} onPointerDown={e=>boxDown(e,k,'resize')}/>} 
        </div>;
      })}
    </div>
    <p className="hint">El video puede seguir reproduciéndose mientras mueves o redimensionas los cuadros. La vista vertical se sincroniza con este mismo punto del video.</p>
  </div>
}
