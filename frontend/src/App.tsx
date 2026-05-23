import { useEffect, useState } from "react";
import {
  AzureCuAnalyzer,
  DetectedPart,
  DetectionMetrics,
  EngineName,
  HeaderPosition,
  PageData,
  RunSummary,
  TitlePosition,
  downloadUrl,
  fetchAzureCuAnalyzers,
  getPreview,
  reanalyze,
  uploadPdf,
} from "./api";
import PreviewView from "./components/PreviewView";
import UploadView from "./components/UploadView";

const ANALYZERS_CACHE_KEY = "azurecu_analyzers_cache_v1";
const CU_SELECTION_KEY = "azurecu_selection_v1";

type AppState =
  | { screen: "upload" }
  | {
      screen: "preview";
      sessionId: string;
      pages: PageData[];
      parts: DetectedPart[];
      activeEngine: EngineName;
      activeEngineLabel: string;
      metrics: DetectionMetrics | null;
      hasDownloadableResult: boolean;
      runs: Record<string, RunSummary>;
    };

export default function App() {
  const [state, setState] = useState<AppState>({ screen: "upload" });
  const [selectedEngine, setSelectedEngine] = useState<EngineName>("azure_cu");
  const [selectedTitlePosition, setSelectedTitlePosition] = useState<TitlePosition>("top");
  const [selectedHeaderPosition, setSelectedHeaderPosition] = useState<HeaderPosition>("right");
  const [selectedCuAnalyzerId, setSelectedCuAnalyzerId] = useState<string>("");
  const [selectedCuApiVersion, setSelectedCuApiVersion] = useState<string>("");
  const [azureCuAnalyzers, setAzureCuAnalyzers] = useState<AzureCuAnalyzer[]>([]);
  const [analyzersFetchedAt, setAnalyzersFetchedAt] = useState<string | null>(null);
  const [isLoadingAnalyzers, setIsLoadingAnalyzers] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(ANALYZERS_CACHE_KEY);
      if (raw) {
        const obj = JSON.parse(raw) as { analyzers?: AzureCuAnalyzer[]; fetched_at?: string };
        if (Array.isArray(obj.analyzers)) setAzureCuAnalyzers(obj.analyzers);
        if (typeof obj.fetched_at === "string") setAnalyzersFetchedAt(obj.fetched_at);
      }
    } catch {
      // ignore cache parse errors
    }

    try {
      const raw = localStorage.getItem(CU_SELECTION_KEY);
      if (raw) {
        const obj = JSON.parse(raw) as { analyzer_id?: string; api_version?: string };
        if (typeof obj.analyzer_id === "string") setSelectedCuAnalyzerId(obj.analyzer_id);
        if (typeof obj.api_version === "string") setSelectedCuApiVersion(obj.api_version);
      }
    } catch {
      // ignore cache parse errors
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        ANALYZERS_CACHE_KEY,
        JSON.stringify({ analyzers: azureCuAnalyzers, fetched_at: analyzersFetchedAt }),
      );
    } catch {
      // ignore storage errors
    }
  }, [azureCuAnalyzers, analyzersFetchedAt]);

  useEffect(() => {
    try {
      localStorage.setItem(
        CU_SELECTION_KEY,
        JSON.stringify({ analyzer_id: selectedCuAnalyzerId, api_version: selectedCuApiVersion }),
      );
    } catch {
      // ignore storage errors
    }
  }, [selectedCuAnalyzerId, selectedCuApiVersion]);

  async function loadPreview(sessionId: string) {
    const preview = await getPreview(sessionId);
    setSelectedEngine(preview.active_engine);
    setSelectedTitlePosition(preview.title_position);
    setSelectedHeaderPosition(preview.header_position);
    setSelectedCuAnalyzerId(preview.cu_analyzer_id ?? "");
    setSelectedCuApiVersion(preview.cu_api_version ?? "");
    setState({
      screen: "preview",
      sessionId,
      pages: preview.pages,
      parts: preview.parts,
      activeEngine: preview.active_engine,
      activeEngineLabel: preview.active_engine_label,
      metrics: preview.metrics,
      hasDownloadableResult: preview.has_downloadable_result,
      runs: preview.runs,
    });
  }

  async function handleUpload(
    file: File,
    engine: EngineName,
    titlePosition: TitlePosition,
    headerPosition: HeaderPosition,
  ) {
    setIsLoading(true);
    setError(null);
    try {
      const { session_id } = await uploadPdf(
        file,
        engine,
        titlePosition,
        headerPosition,
        selectedCuAnalyzerId || undefined,
        selectedCuApiVersion || undefined,
      );
      await loadPreview(session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleFetchAnalyzers() {
    setIsLoadingAnalyzers(true);
    setError(null);
    try {
      const res = await fetchAzureCuAnalyzers(selectedCuApiVersion || undefined);
      setAzureCuAnalyzers(res.analyzers);
      setAnalyzersFetchedAt(res.fetched_at);
      if (!selectedCuApiVersion) setSelectedCuApiVersion(res.api_version);
      if (!selectedCuAnalyzerId && res.analyzers[0]) {
        setSelectedCuAnalyzerId(res.analyzers[0].analyzer_id);
        setSelectedCuApiVersion(res.analyzers[0].api_version);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analyzer一覧の取得に失敗しました");
    } finally {
      setIsLoadingAnalyzers(false);
    }
  }

  async function handleEngineSwitch(engine: EngineName) {
    if (state.screen !== "preview") return;
    if (engine === state.activeEngine) return;
    setIsLoading(true);
    setError(null);
    try {
      await reanalyze(state.sessionId, engine);
      setSelectedEngine(engine);
      await loadPreview(state.sessionId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "再解析に失敗しました");
    } finally {
      setIsLoading(false);
    }
  }

  function handleDownload() {
    if (state.screen !== "preview") return;
    const url = downloadUrl(state.sessionId);
    const a = document.createElement("a");
    a.href = url;
    a.download = "parts.zip";
    a.click();
  }

  function handleReset() {
    setState({ screen: "upload" });
    setError(null);
  }

  if (state.screen === "preview") {
    return (
      <PreviewView
        sessionId={state.sessionId}
        pages={state.pages}
        parts={state.parts}
        activeEngine={state.activeEngine}
        activeEngineLabel={state.activeEngineLabel}
        metrics={state.metrics}
        hasDownloadableResult={state.hasDownloadableResult}
        runs={state.runs}
        isLoading={isLoading}
        onEngineSwitch={handleEngineSwitch}
        onDownload={handleDownload}
        onReset={handleReset}
      />
    );
  }

  return (
    <>
      <UploadView
        selectedEngine={selectedEngine}
        selectedTitlePosition={selectedTitlePosition}
        selectedHeaderPosition={selectedHeaderPosition}
        selectedCuAnalyzerId={selectedCuAnalyzerId}
        selectedCuApiVersion={selectedCuApiVersion}
        analyzerOptions={azureCuAnalyzers}
        analyzersFetchedAt={analyzersFetchedAt}
        isLoadingAnalyzers={isLoadingAnalyzers}
        onEngineChange={setSelectedEngine}
        onTitlePositionChange={setSelectedTitlePosition}
        onHeaderPositionChange={setSelectedHeaderPosition}
        onCuAnalyzerChange={setSelectedCuAnalyzerId}
        onCuApiVersionChange={setSelectedCuApiVersion}
        onFetchAnalyzers={handleFetchAnalyzers}
        onUpload={handleUpload}
        isLoading={isLoading}
      />
      {error && (
        <div style={errorStyle}>
          <strong>エラー:</strong> {error}
        </div>
      )}
    </>
  );
}

const errorStyle: React.CSSProperties = {
  position: "fixed",
  bottom: "1.5rem",
  left: "50%",
  transform: "translateX(-50%)",
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fca5a5",
  borderRadius: 8,
  padding: "0.75rem 1.25rem",
  fontSize: "0.9rem",
  maxWidth: 480,
  textAlign: "center",
};
