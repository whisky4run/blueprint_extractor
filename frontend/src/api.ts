const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DetectedPart {
  title: string;
  bbox: BoundingBox;
  page: number;
}

export interface UploadResponse {
  session_id: string;
  pages: number;
  parts: DetectedPart[];
}

export interface PageData {
  filename: string;
  data: string; // base64 PNG
}

export interface PreviewResponse {
  session_id: string;
  pages: PageData[];
  parts: DetectedPart[];
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function getPreview(sessionId: string): Promise<PreviewResponse> {
  const res = await fetch(`${BASE_URL}/api/preview/${sessionId}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export function downloadUrl(sessionId: string): string {
  return `${BASE_URL}/api/download/${sessionId}`;
}
