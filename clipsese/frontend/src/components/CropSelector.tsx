import { useRef, useState } from 'react';
import type { Crop } from '../types';

type Props = {
  videoUrl: string;
  currentTime: number;
  crops: Record<string, Crop>;
  active: string;
  onActive: (name:string)=>void;
  onCrop: (name:string,crop:Crop)=>void;
};

const labels: Record<string,string> = {camera1:'Cámara 1',camera2:'Cámara 2',content:'Contenido'};

export default function CropSelector({videoUrl,currentTime,crops,active,onActive,onCrop}:Props){
  const wrap=useRef<HTMLDivElement>(null);
  const video=useRef<HTMLVideoElement>(null);
  const [drag,setDrag]=useState<{x:number;y:number}|null>(null);

  function point(e: React.PointerEvent){
    const r=wrap.current!.getBoundingClientRect();
    return {x:Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))};
  }
  function down(e:React.PointerEvent){
    e.currentTarget.setPointerCapture(e.pointerId); setDrag(point(e));
  }
  function move(e:React.PointerEvent){
    if(!drag) return; const p=point(e);
    const x=Math.min(drag.x,p.x), y=Math.min(drag.y,p.y), w=Math.max(.03,Math.abs(p.x-drag.x)), h=Math.max(.03,Math.abs(p.y-drag.y));
    onCrop(active,{x,y,w:Math.min(w,1-x),h:Math.min(h,1-y)});
  }
  function up(){setDrag(null)}
  function sync(){ if(video.current && Math.abs(video.current.currentTime-currentTime)>.4) video.current.currentTime=currentTime; }
  return <div>
    <div className="crop-tabs">{Object.keys(crops).map(k=><button key={k} className={active===k?'active':''} onClick={()=>onActive(k)}>{labels[k]}</button>)}</div>
    <div className="video-crop-wrap" ref={wrap} onPointerDown={down} onPointerMove={move} onPointerUp={up}>
      <video ref={video} src={videoUrl} controls onLoadedMetadata={sync} onSeeked={sync}/>
      {Object.entries(crops).map(([k,c])=><div key={k} className={`crop-box ${active===k?'selected':''}`} style={{left:`${c.x*100}%`,top:`${c.y*100}%`,width:`${c.w*100}%`,height:`${c.h*100}%`}}><span>{labels[k]}</span></div>)}
    </div>
    <p className="hint">Elige una zona y arrastra sobre el video para marcarla. El render final usa el archivo original, no este preview.</p>
  </div>
}
