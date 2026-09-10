export type Crop = { x: number; y: number; w: number; h: number };
export type Layout = 'one_media' | 'two_cameras' | 'two_media';
export type Project = {
  id: string;
  status: string;
  original_name: string;
  preview_file: string;
  metadata: { duration: number; width: number; height: number; fps: string };
  transcript_status: string;
  transcript_error?: string;
  media?: Media[];
  renders?: RenderItem[];
};
export type Media = { id: string; file: string; name: string; type: 'image' | 'video'; source_url?: string };
export type RenderItem = { id: string; file: string; start: number; end: number; layout: Layout };
export type SearchResult = { start: number; end: number; text: string; score: number };
