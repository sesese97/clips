import type { Crop, Layout, Project, SearchResult } from '../types';

export const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

async function request(input: RequestInfo | URL, init?: RequestInit) {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error('No se pudo conectar con el servidor de ClipSese. Revisa que Railway esté Online.');
  }
}

export async function createProject(file?: File, youtubeUrl?: string): Promise<Project> {
  const fd = new FormData();
  if (file) fd.append('file', file);
  if (youtubeUrl) fd.append('youtube_url', youtubeUrl);
  return json(await request(`${API}/api/projects`, { method: 'POST', body: fd }));
}

export async function getProject(id: string): Promise<Project> {
  return json(await request(`${API}/api/projects/${id}`));
}

export async function startTranscription(id: string) {
  return json(await request(`${API}/api/projects/${id}/transcribe`, { method: 'POST' }));
}

export async function searchTranscript(id: string, mode: 'keyword' | 'theme', query: string): Promise<SearchResult[]> {
  const data = await json<{results: SearchResult[]}>(await request(`${API}/api/projects/${id}/search`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({mode, query, max_results: 8})
  }));
  return data.results;
}

export async function addMedia(id: string, file?: File, url?: string) {
  const fd = new FormData();
  if (file) fd.append('file', file);
  if (url) fd.append('url', url);
  return json(await request(`${API}/api/projects/${id}/media`, {method:'POST', body:fd}));
}

export async function renderClip(id: string, body: {
  start:number; end:number; layout:Layout; camera1:Crop; camera2?:Crop; content?:Crop; media_id?:string
}) {
  return json<{id:string;file:string}>(await request(`${API}/api/projects/${id}/render`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  }));
}

export const fileUrl = (projectId: string, file: string) => `${API}/files/${projectId}/${encodeURIComponent(file)}`;
