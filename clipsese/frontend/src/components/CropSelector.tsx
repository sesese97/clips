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

type Gesture =
  | {type:'draw';start:{x:number;y:number}}
  | {type:'move'|'resize';start:{x:number;y:number};original:Crop}
  | null;

const labels: Record<string,string> = {camera1:'Cámara 1',camera2:'Cámara 2',content:'Contenido'};
const cropKeys=['camera1','camera2','content'];

export default function CropSelector({videoUrl,currentTime,crops,active,onActive,onCrop}:Props){
  const wrap=useRef<HTMLDivElement>(null);
  const video=useRef<HTMLVideoElement>(null);
  const [gesture,setGesture]=useState<Gesture>(null);

  function point(e: React.PointerEvent){
    const r=wrap.current!.getBoundingClientRect();
    return {x:Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y:Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))};
  }
  function backgroundDown(e:React.PointerEvent){
    if((e.target as HTMLElement).closest('.crop-box'))return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setGesture({type:'draw',start:point(e)});
  }
  function boxDown(e:React.PointerEvent,name:string,type:'move'|'resize'){
    e.stopPropagation();
    onActive(name);
    wrap.current?.setPointerCapture(e.pointerId);
    setGesture({type,start:point(e),original:{...crops[name]}});
  }
  function move(e:React.PointerEvent){
    if(!gesture)return;
    const p=point(e);
    if(gesture.type==='draw'){
      const x=Math.min(gesture.start.x,p.x), y=Math.min(gesture.start.y,p.y);
      const w=Math.max(.03,Math.abs(p.x-gesture.start.x)), h=Math.max(.03,Math.abs(p.y-gesture.start.y));
      onCrop(active,{x,y,w:Math.min(w,1-x),h:Math.min(h,1-y)});
      return;
    }
    const dx=p.x-gesture.start.x,dy=p.y-gesture.start.y;
    const o=gesture.original;
    if(gesture.type==='move'){
      const x=Math.max(0,Math.min(1-o.w,o.x+dx));
      const y=Math.max(0,Math.min(1-o.h,o.y+dy));
      onCrop(active,{...o,x,y});
    }else{
      const w=Math.max(.03,Math.min(1-o.x,o.w+dx));
      const h=Math.max(.03,Math.min(1-o.y,o.h+dy));
      onCrop(active,{...o,w,h});
    }
  }
  function up(){setGesture(null)}
  function sync(){ if(video.current && Math.abs(video.current.currentTime-currentTime)>.4) video.current.currentTime=currentTime; }

  return <div>
    <div className="crop-tabs">{cropKeys.filter(k=>crops[k]).map(k=><button key={k} className={active===k?'active':''} onClick={()=>onActive(k)}>{labels[k]}</button>)}</div>
    <div className="video-crop-wrap" ref={wrap} onPointerDown={backgroundDown} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
      <video ref={video} src={videoUrl} controls onLoadedMetadata={sync} onSeeked={sync}/>
      {cropKeys.filter(k=>crops[k]).map(k=>{
        const c=crops[k];
        return <div key={k} data-crop={k} className={`crop-box ${active===k?'selected':''}`} onPointerDown={e=>boxDown(e,k,'move')} style={{left:`${c.x*100}%`,top:`${c.y*100}%`,width:`${c.w*100}%`,height:`${c.h*100}%`}}>
          <span>{labels[k]}</span>
          {active===k&&<i className="crop-resize" onPointerDown={e=>boxDown(e,k,'resize')}/>} 
        </div>;
      })}
    </div>
    <p className="hint">Arrastra dentro de un cuadro para moverlo. Usa la esquina inferior derecha para cambiar su tamaño. Arrastrar fuera de los cuadros crea una selección nueva.</p>
  </div>
}
