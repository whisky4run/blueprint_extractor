const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export type EngineName = "opencv" | "azure_cu";
export type TitlePosition = "top" | "bottom" | "left" | "right";
export type HeaderPosition = "top" | "bottom" | "left" | "right";

export const ENGINE_OPTIONS: Array<{ value: EngineName; label: string }> = [
  { value: "opencv", label: "OpenCV切り出し" },
  { value: "azure_cu", label: "AzureCU切り出し" },
];

export const TITLE_POSITION_OPTIONS: Array<{ value: TitlePosition; label: string }> = [
  { value: "top", label: "上" },
  { value: "bottom", label: "下" },
  { value: "left", label: "左" },
  { value: "right", label: "右" },
];

export const HEADER_POSITION_OPTIONS: Array<{ value: HeaderPosition; label: string }> = [
  { value: "right", label: "右" },
  { value: "left", label: "左" },
  { value: "top", label: "上" },
  { value: "bottom", label: "下" },
];

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

export interface HeaderFieldItem {
  key: string;
  value: string;
  page: number | null;
  bbox: BoundingBox | null;
  source: string | null;
}

export interface UploadResponse {
  session_id: string;
  pages: number;
  engine: EngineName;
  parts: DetectedPart[];
  metrics: DetectionMetrics;
}

export interface PrepareResponse {
  session_id: string;
  pages: number;
}

export interface PageData {
  filename: string;
  data: string; // base64 PNG
}

export interface PreviewResponse {
  session_id: string;
  pages: PageData[];
  active_engine: EngineName;
  active_engine_label: string;
  title_position: TitlePosition;
  header_position: HeaderPosition;
  cu_contents_analyzer_id: string | null;
  cu_contents_api_version: string | null;
  cu_header_analyzer_id: string | null;
  cu_header_api_version: string | null;
  parts: DetectedPart[];
  header_fields: HeaderFieldItem[];
  metrics: DetectionMetrics | null;
  has_downloadable_result: boolean;
  runs: Record<string, RunSummary>;
}

export interface AzureCuAnalyzer {
  analyzer_id: string;
  description: string;
  status: string;
  created_at: string | null;
  last_modified_at: string | null;
  api_version: string;
}

export interface AzureCuAnalyzersResponse {
  api_version: string;
  count: number;
  fetched_at: string;
  analyzers: AzureCuAnalyzer[];
}

export interface UiPreferences {
  cu_selection: {
    contents_analyzer_id: string;
    contents_api_version: string;
    header_analyzer_id: string;
    header_api_version: string;
  };
  analyzer_cache: {
    api_version: string;
    fetched_at: string | null;
    analyzers: AzureCuAnalyzer[];
  };
}

export interface DetectionMetrics {
  process_ms: number;
  parts_count: number;
  failure_reason: string | null;
}

export interface RunSummary {
  engine_label: string;
  executed_at: string;
  metrics: DetectionMetrics;
}

export interface ReanalyzeResponse {
  session_id: string;
  engine: EngineName;
  parts: DetectedPart[];
  metrics: DetectionMetrics;
  executed_at: string;
}

export async function uploadPdf(
  file: File,
  engine: EngineName,
  titlePosition: TitlePosition,
  headerPosition: HeaderPosition,
  cuContentsAnalyzerId?: string | null,
  cuContentsApiVersion?: string | null,
  cuHeaderAnalyzerId?: string | null,
  cuHeaderApiVersion?: string | null,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("engine", engine);
  form.append("title_position", titlePosition);
  form.append("header_position", headerPosition);
  if (cuContentsAnalyzerId) form.append("cu_contents_analyzer_id", cuContentsAnalyzerId);
  if (cuContentsApiVersion) form.append("cu_contents_api_version", cuContentsApiVersion);
  if (cuHeaderAnalyzerId) form.append("cu_header_analyzer_id", cuHeaderAnalyzerId);
  if (cuHeaderApiVersion) form.append("cu_header_api_version", cuHeaderApiVersion);
  const res = await fetch(`${BASE_URL}/api/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function preparePdf(
  file: File,
  engine: EngineName,
  titlePosition: TitlePosition,
  headerPosition: HeaderPosition,
  cuContentsAnalyzerId?: string | null,
  cuContentsApiVersion?: string | null,
  cuHeaderAnalyzerId?: string | null,
  cuHeaderApiVersion?: string | null,
): Promise<PrepareResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("engine", engine);
  form.append("title_position", titlePosition);
  form.append("header_position", headerPosition);
  if (cuContentsAnalyzerId) form.append("cu_contents_analyzer_id", cuContentsAnalyzerId);
  if (cuContentsApiVersion) form.append("cu_contents_api_version", cuContentsApiVersion);
  if (cuHeaderAnalyzerId) form.append("cu_header_analyzer_id", cuHeaderAnalyzerId);
  if (cuHeaderApiVersion) form.append("cu_header_api_version", cuHeaderApiVersion);
  const res = await fetch(`${BASE_URL}/api/prepare`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function runPrepared(
  sessionId: string,
  engine: EngineName,
  titlePosition: TitlePosition,
  headerPosition: HeaderPosition,
  cuContentsAnalyzerId?: string | null,
  cuContentsApiVersion?: string | null,
  cuHeaderAnalyzerId?: string | null,
  cuHeaderApiVersion?: string | null,
): Promise<ReanalyzeResponse> {
  const form = new FormData();
  form.append("engine", engine);
  form.append("title_position", titlePosition);
  form.append("header_position", headerPosition);
  if (cuContentsAnalyzerId) form.append("cu_contents_analyzer_id", cuContentsAnalyzerId);
  if (cuContentsApiVersion) form.append("cu_contents_api_version", cuContentsApiVersion);
  if (cuHeaderAnalyzerId) form.append("cu_header_analyzer_id", cuHeaderAnalyzerId);
  if (cuHeaderApiVersion) form.append("cu_header_api_version", cuHeaderApiVersion);
  const res = await fetch(`${BASE_URL}/api/run/${sessionId}`, { method: "POST", body: form });
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

export async function reanalyze(sessionId: string, engine: EngineName): Promise<ReanalyzeResponse> {
  const res = await fetch(`${BASE_URL}/api/reanalyze/${sessionId}?engine=${engine}`, {
    method: "POST",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function fetchAzureCuAnalyzers(apiVersion?: string): Promise<AzureCuAnalyzersResponse> {
  const qp = apiVersion ? `?api_version=${encodeURIComponent(apiVersion)}` : "";
  const res = await fetch(`${BASE_URL}/api/azurecu/analyzers${qp}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function getUiPreferences(): Promise<UiPreferences> {
  const res = await fetch(`${BASE_URL}/api/ui/preferences`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export async function putUiPreferences(prefs: UiPreferences): Promise<UiPreferences> {
  const res = await fetch(`${BASE_URL}/api/ui/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json();
}

export function downloadUrl(sessionId: string): string {
  return `${BASE_URL}/api/download/${sessionId}`;
}
