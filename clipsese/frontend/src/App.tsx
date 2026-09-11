import { useEffect, useState } from 'react';
import { Download, Film, Link as LinkIcon, Search, Upload, Wand2 } from 'lucide-react';
import CropSelector from './components/CropSelector';
import VerticalPreview from './components/VerticalPreview';
import { addMedia, createProject, fileUrl, getProject, renderClip, searchTranscript, startTranscription } from './lib/api';
import type { Crop, Layout, Project, SearchResult } from './types';

const defaultCrops:Record<string,Crop>={
  camera1:{x:.04,y:.08,w:.42,h:.75}, camera2:{x:.52,y:.08,w:.42,h:.75}, content:{x:.44,y:.04,w:.54,h:.9}
};
function sec(v:number){const m=Math.floor(v/60),s=Math.floor(v%60);return `${m}:${String(s).padStart(2,'0')}`}

const importLabels:Record<string,string>={
  queued:'Preparando importación…',
  connecting:'Conectando con YouTube y validando acceso…',
  preparing_proxy:'Preparando una copia ligera para editar…',
  downloading:'Conectando con YouTube…',
  analyzing:'Analizando video…',
  preparing_preview:'Preparando vista previa…',
  ready:'Listo',
  error:'Error al importar'
};

export default function App(){
  const [project,setProject]=useState<Project|null>(null); const [yt,setYt]=useState(''); const [loading,setLoading]=useState(''); const [err,setErr]=useState('');
  const [start,setStart]=useState(0); const [end,setEnd]=useState(30); const [mode,setMode]=useState<'time'|'keyword'|'theme'>('time'); const [query,setQuery]=useState(''); const [results,setResults]=useState<SearchResult[]>([]);
  const [layout,setLayout]=useState<Layout>('one_media'); const [crops,setCrops]=useState(defaultCrops); const [activeCrop,setActiveCrop]=useState('camera1'); const [mediaId,setMediaId]=useState<string>(''); const [mediaUrl,setMediaUrl]=useState('');
  const preview=project?.preview_file?fileUrl(project.id,project.preview_file):''; const selectedMedia=project?.media?.find(m=>m.id===mediaId);
  const duration=project?.metadata?.duration||0;
  const clipLen=Math.max(0,end-start);

  async function refresh(){if(project){const p=await getProject(project.id);setProject(p);return p}}

  useEffect(()=>{
    if(!project)return;
    const shouldPoll=project.status==='importing'||project.transcript_status==='processing';
    if(!shouldPoll)return;
    const id=project.id;
    const previousStatus=project.status;
    const poll=async()=>{
      try{
        const p=await getProject(id);
        setProject(p);
        if(previousStatus!=='ready'&&p.status==='ready'){
          setStart(0);
          setEnd(Math.min(30,p.metadata?.duration||30));
          setErr('');
        }
        if(p.status==='error') setErr(p.import_error||'No se pudo importar el video.');
      }catch(e:any){
        setErr(e.message||'No se pudo consultar el estado de la importación.');
      }
    };
    poll();
    const t=setInterval(poll,2500);
    return()=>clearInterval(t);
  },[project?.id,project?.status,project?.transcript_status]);

  async function ingest(file?:File){
    setErr('');
    setLoading(file?'Subiendo archivo…':'Iniciando importación…');
    try{
      const p=await createProject(file,file?undefined:yt);
      setProject(p);
      if(p.status==='ready'){
        setEnd(Math.min(30,p.metadata?.duration||30));
        setStart(0);
      }
    }catch(e:any){setErr(e.message)}finally{setLoading('')}
  }
  async function transcribe(){if(!project)return;setLoading('Iniciando transcripción…');try{await startTranscription(project.id);await refresh()}catch(e:any){setErr(e.message)}finally{setLoading('')}}
  async function doSearch(){if(!project||mode==='time'||!query.trim())return;setLoading('Buscando…');try{setResults(await searchTranscript(project.id,mode,query))}catch(e:any){setErr(e.message)}finally{setLoading('')}}
  async function uploadMedia(file?:File){if(!project||!file)return;setLoading('Subiendo multimedia…');try{const m:any=await addMedia(project.id,file);await refresh();setMediaId(m.id)}catch(e:any){setErr(e.message)}finally{setLoading('')}}
  async function importMediaUrl(){if(!project||!mediaUrl.trim())return;setLoading('Importando multimedia…');try{const m:any=await addMedia(project.id,undefined,mediaUrl.trim());await refresh();setMediaId(m.id);setMediaUrl('')}catch(e:any){setErr(e.message)}finally{setLoading('')}}
  async function render(){if(!project)return;if(clipLen<=0||clipLen>30){setErr('El clip debe durar entre 0 y 30 segundos');return}setLoading(project.source_url?'Obteniendo el tramo en máxima calidad y renderizando…':'Renderizando a 1080×1920…');try{const body:any={start,end,layout,camera1:crops.camera1};if(layout!=='one_media')body.camera2=crops.camera2;if(layout!=='two_cameras'){if(mediaId)body.media_id=mediaId;else body.content=crops.content}const r=await renderClip(project.id,body);await refresh();window.open(fileUrl(project.id,r.file),'_blank')}catch(e:any){setErr(e.message)}finally{setLoading('')}}

  return <div className="app-shell">
    <aside><div className="brand">CLIP<span>SESE</span><small>Tu contenido, más lejos</small></div><nav><a className="active"><Film size={18}/>Nuevo clip</a><a><Wand2 size={18}/>Layouts</a></nav><div className="aside-note">MVP privado para clips de hasta 30 s. Usa contenido propio o con autorización.</div></aside>
    <main>
      <header><div><h1>Creador de clips verticales</h1><p>YouTube o archivo original → busca el momento → acomoda cámaras → exporta.</p></div><div className="quality">1080 × 1920 · H.264 · CRF 17</div></header>
      {err&&<div className="error" onClick={()=>setErr('')}>{err}</div>}{loading&&<div className="loading">{loading}</div>}

      {!project?
        <section className="card import-card"><h2>1. Importar video</h2><div className="import-grid"><div><label>Enlace de YouTube</label><div className="row"><input value={yt} onChange={e=>setYt(e.target.value)} placeholder="https://youtube.com/watch?v=…"/><button onClick={()=>ingest()} disabled={!yt}><LinkIcon size={16}/>Cargar</button></div></div><div className="upload-box"><Upload/><strong>Archivo original</strong><span>Máxima calidad. MP4/MOV/WebM.</span><input type="file" accept="video/*" onChange={e=>ingest(e.target.files?.[0])}/></div></div></section>
      :project.status!=='ready'?
        <section className="card import-card">
          <h2>{project.status==='error'?'No se pudo importar':'Preparando video'}</h2>
          <p>{project.status==='error'?(project.import_error||'La importación falló.'):(importLabels[project.import_stage||'queued']||'Procesando video…')}</p>
          {project.status==='importing'&&<p style={{opacity:.7}}>Para YouTube se prepara sólo una copia ligera de edición. La máxima calidad se obtiene únicamente al exportar el clip.</p>}
          <button className="ghost" onClick={()=>{setProject(null);setErr('')}}>{project.status==='error'?'Intentar otro video':'Cancelar / cambiar video'}</button>
        </section>
      :<>
      <section className="card projectbar"><div><b>{project.original_name}</b><span>{project.metadata.width}×{project.metadata.height} · {sec(project.metadata.duration)}</span></div><button className="ghost" onClick={()=>setProject(null)}>Cambiar video</button></section>
      <div className="workspace">
        <div className="leftcol">
          <section className="card"><div className="section-head"><div><h2>2. Encontrar el momento</h2><p>Tiempo exacto, jugador/palabra o búsqueda temática.</p></div>{project.transcript_status!=='ready'&&<button onClick={transcribe} disabled={project.transcript_status==='processing'}>{project.transcript_status==='processing'?'Transcribiendo…':'Analizar audio'}</button>}</div>
            <div className="mode-tabs"><button className={mode==='time'?'active':''} onClick={()=>setMode('time')}>Por tiempo</button><button className={mode==='keyword'?'active':''} onClick={()=>setMode('keyword')}>Jugador / palabra</button><button className={mode==='theme'?'active':''} onClick={()=>setMode('theme')}>Tema (IA)</button></div>
            {mode==='time'?<div className="time-grid"><label>Inicio<input type="number" step=".1" min="0" max={duration} value={start} onChange={e=>setStart(+e.target.value)}/></label><label>Fin<input type="number" step=".1" min="0" max={duration} value={end} onChange={e=>setEnd(+e.target.value)}/></label><div className={clipLen>30?'duration bad':'duration'}>{clipLen.toFixed(1)} s / 30 s</div></div>:<div><div className="row"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==='Enter'&&doSearch()} placeholder={mode==='keyword'?'Ej. Javonte Williams':'Ej. cuando hablamos de RB baratos'}/><button onClick={doSearch}><Search size={16}/>Buscar</button></div><div className="results">{results.map((r,i)=><button key={i} className="result" onClick={()=>{setStart(r.start);setEnd(Math.min(r.end,r.start+30))}}><b>{sec(r.start)} – {sec(r.end)}</b><span>{r.text.slice(0,220)}</span><em>{Math.round(r.score*100)}%</em></button>)}</div></div>}
            {project.transcript_status==='error'&&<p className="error-inline">{project.transcript_error}</p>}
          </section>
          <section className="card"><h2>3. Marcar las zonas del video</h2><CropSelector videoUrl={preview} currentTime={start} crops={crops} active={activeCrop} onActive={setActiveCrop} onCrop={(k,c)=>setCrops(v=>({...v,[k]:c}))}/></section>
        </div>
        <div className="rightcol">
          <section className="card sticky"><h2>4. Layout vertical</h2><div className="layout-buttons"><button className={layout==='one_media'?'active':''} onClick={()=>setLayout('one_media')}><i className="layout-icon one"></i>1 cámara + multimedia</button><button className={layout==='two_cameras'?'active':''} onClick={()=>setLayout('two_cameras')}><i className="layout-icon two"></i>2 cámaras</button><button className={layout==='two_media'?'active':''} onClick={()=>setLayout('two_media')}><i className="layout-icon three"></i>2 cámaras + multimedia</button></div>
            <VerticalPreview projectId={project.id} videoUrl={preview} layout={layout} crops={crops} media={selectedMedia} currentTime={start}/>
            {layout!=='two_cameras'&&<div className="media-panel"><h3>Multimedia</h3><p>Si no eliges un archivo, se usa el recorte “Contenido” del video original.</p><label className="mini-upload"><Upload size={15}/>Subir imagen/video<input type="file" accept="image/*,video/*" onChange={e=>uploadMedia(e.target.files?.[0])}/></label><div className="row"><input value={mediaUrl} onChange={e=>setMediaUrl(e.target.value)} placeholder="YouTube, X o TikTok"/><button className="ghost" onClick={importMediaUrl}>Importar</button></div>{project.media&&project.media.length>0&&<select value={mediaId} onChange={e=>setMediaId(e.target.value)}><option value="">Usar recorte del video</option>{project.media.map(m=><option key={m.id} value={m.id}>{m.name.slice(0,48)}</option>)}</select>}</div>}
            <div className="clip-summary"><span>Inicio <b>{sec(start)}</b></span><span>Fin <b>{sec(end)}</b></span><span>Duración <b>{clipLen.toFixed(1)} s</b></span></div><button className="export" onClick={render} disabled={clipLen<=0||clipLen>30}><Download size={18}/>Exportar máxima calidad</button>
            {project.renders&&project.renders.length>0&&<div className="recent"><h3>Exports recientes</h3>{project.renders.slice(0,3).map(r=><a key={r.id} href={fileUrl(project.id,r.file)} target="_blank">{r.file} · {sec(r.end-r.start)}</a>)}</div>}
          </section>
        </div>
      </div></>}
    </main>
  </div>
}
