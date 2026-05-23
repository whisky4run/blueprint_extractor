import { useEffect, useState } from "react";
import {
  AzureCuAnalyzer,
  DetectedPart,
  DetectionMetrics,
  EngineName,
  HeaderFieldItem,
  HeaderPosition,
  PageData,
  RunSummary,
  TitlePosition,
  downloadUrl,
  fetchAzureCuAnalyzers,
  getUiPreferences,
  getPreview,
  preparePdf,
  putUiPreferences,
  reanalyze,
  runPrepared,
  UiPreferences,
} from "./api";
import PreviewView from "./components/PreviewView";
import UploadView from "./components/UploadView";

type AppState =
  | { screen: "upload" }
  | {
      screen: "preview";
      sessionId: string;
      pages: PageData[];
      parts: DetectedPart[];
      headerFields: HeaderFieldItem[];
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
  const [selectedCuContentsAnalyzerId, setSelectedCuContentsAnalyzerId] = useState<string>("");
  const [selectedCuContentsApiVersion, setSelectedCuContentsApiVersion] = useState<string>("");
  const [selectedCuHeaderAnalyzerId, setSelectedCuHeaderAnalyzerId] = useState<string>("");
  const [selectedCuHeaderApiVersion, setSelectedCuHeaderApiVersion] = useState<string>("");
  const [azureCuAnalyzers, setAzureCuAnalyzers] = useState<AzureCuAnalyzer[]>([]);
  const [analyzersFetchedAt, setAnalyzersFetchedAt] = useState<string | null>(null);
  const [isLoadingAnalyzers, setIsLoadingAnalyzers] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPrefsReady, setIsPrefsReady] = useState(false);
  const [preparedSessionId, setPreparedSessionId] = useState<string | null>(null);
  const [preparedPages, setPreparedPages] = useState<PageData[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function loadPrefs() {
      try {
        const prefs = await getUiPreferences();
        if (cancelled) return;
        setSelectedCuContentsAnalyzerId(prefs.cu_selection.contents_analyzer_id || "");
        setSelectedCuContentsApiVersion(prefs.cu_selection.contents_api_version || "");
        setSelectedCuHeaderAnalyzerId(prefs.cu_selection.header_analyzer_id || "");
        setSelectedCuHeaderApiVersion(prefs.cu_selection.header_api_version || "");
        setAzureCuAnalyzers(Array.isArray(prefs.analyzer_cache.analyzers) ? prefs.analyzer_cache.analyzers : []);
        setAnalyzersFetchedAt(prefs.analyzer_cache.fetched_at ?? null);
      } catch {
        // backend preference load failure should not block app usage
      } finally {
        if (!cancelled) setIsPrefsReady(true);
      }
    }
    void loadPrefs();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isPrefsReady) return;
    const timer = window.setTimeout(() => {
      const payload: UiPreferences = {
        cu_selection: {
          contents_analyzer_id: selectedCuContentsAnalyzerId,
          contents_api_version: selectedCuContentsApiVersion,
          header_analyzer_id: selectedCuHeaderAnalyzerId,
          header_api_version: selectedCuHeaderApiVersion,
        },
        analyzer_cache: {
          api_version: selectedCuContentsApiVersion || selectedCuHeaderApiVersion || "",
          fetched_at: analyzersFetchedAt,
          analyzers: azureCuAnalyzers,
        },
      };
      void putUiPreferences(payload).catch(() => {
        // backend preference save failure should not block app usage
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [
    isPrefsReady,
    selectedCuContentsAnalyzerId,
    selectedCuContentsApiVersion,
    selectedCuHeaderAnalyzerId,
    selectedCuHeaderApiVersion,
    azureCuAnalyzers,
    analyzersFetchedAt,
  ]);

  async function loadPreview(sessionId: string) {
    const preview = await getPreview(sessionId);
    setSelectedEngine(preview.active_engine);
    setSelectedTitlePosition(preview.title_position);
    setSelectedHeaderPosition(preview.header_position);
    setSelectedCuContentsAnalyzerId(preview.cu_contents_analyzer_id ?? "");
    setSelectedCuContentsApiVersion(preview.cu_contents_api_version ?? "");
    setSelectedCuHeaderAnalyzerId(preview.cu_header_analyzer_id ?? "");
    setSelectedCuHeaderApiVersion(preview.cu_header_api_version ?? "");
    setState({
      screen: "preview",
      sessionId,
      pages: preview.pages,
      parts: preview.parts,
      headerFields: preview.header_fields,
      activeEngine: preview.active_engine,
      activeEngineLabel: preview.active_engine_label,
      metrics: preview.metrics,
      hasDownloadableResult: preview.has_downloadable_result,
      runs: preview.runs,
    });
  }

  async function handlePrepare(
    file: File,
    engine: EngineName,
    titlePosition: TitlePosition,
    headerPosition: HeaderPosition,
  ) {
    setIsPreparing(true);
    setIsLoading(true);
    setError(null);
    try {
      const { session_id } = await preparePdf(
        file,
        engine,
        titlePosition,
        headerPosition,
        selectedCuContentsAnalyzerId || undefined,
        selectedCuContentsApiVersion || undefined,
        selectedCuHeaderAnalyzerId || undefined,
        selectedCuHeaderApiVersion || undefined,
      );
      const preview = await getPreview(session_id);
      setPreparedSessionId(session_id);
      setPreparedPages(preview.pages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setIsPreparing(false);
      setIsLoading(false);
    }
  }

  async function handleExecute() {
    if (!preparedSessionId) {
      setError("先にPDFを読み込んでください");
      return;
    }
    setIsExecuting(true);
    setIsLoading(true);
    setError(null);
    try {
      await runPrepared(
        preparedSessionId,
        selectedEngine,
        selectedTitlePosition,
        selectedHeaderPosition,
        selectedCuContentsAnalyzerId || undefined,
        selectedCuContentsApiVersion || undefined,
        selectedCuHeaderAnalyzerId || undefined,
        selectedCuHeaderApiVersion || undefined,
      );
      await loadPreview(preparedSessionId);
      setPreparedSessionId(null);
      setPreparedPages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "実行に失敗しました");
    } finally {
      setIsExecuting(false);
      setIsLoading(false);
    }
  }

  async function handleFetchAnalyzers() {
    setIsLoadingAnalyzers(true);
    setError(null);
    try {
      const res = await fetchAzureCuAnalyzers(selectedCuContentsApiVersion || selectedCuHeaderApiVersion || undefined);
      setAzureCuAnalyzers(res.analyzers);
      setAnalyzersFetchedAt(res.fetched_at);
      const headerCandidates = res.analyzers.filter((a) => a.analyzer_id.toLowerCase().startsWith("bph"));
      const contentsCandidates = res.analyzers.filter((a) => a.analyzer_id.toLowerCase().startsWith("bpc"));

      if (!selectedCuHeaderAnalyzerId && headerCandidates[0]) {
        setSelectedCuHeaderAnalyzerId(headerCandidates[0].analyzer_id);
        setSelectedCuHeaderApiVersion(headerCandidates[0].api_version);
      }
      if (!selectedCuContentsAnalyzerId && contentsCandidates[0]) {
        setSelectedCuContentsAnalyzerId(contentsCandidates[0].analyzer_id);
        setSelectedCuContentsApiVersion(contentsCandidates[0].api_version);
      }
      if (!selectedCuHeaderApiVersion && !headerCandidates[0]) {
        setSelectedCuHeaderApiVersion(res.api_version);
      }
      if (!selectedCuContentsApiVersion && !contentsCandidates[0]) {
        setSelectedCuContentsApiVersion(res.api_version);
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
    setPreparedSessionId(null);
    setPreparedPages([]);
    setIsPreparing(false);
    setIsExecuting(false);
    setError(null);
  }

  if (state.screen === "preview") {
    return (
      <PreviewView
        sessionId={state.sessionId}
        pages={state.pages}
        parts={state.parts}
        headerFields={state.headerFields}
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
        selectedCuContentsAnalyzerId={selectedCuContentsAnalyzerId}
        selectedCuContentsApiVersion={selectedCuContentsApiVersion}
        selectedCuHeaderAnalyzerId={selectedCuHeaderAnalyzerId}
        selectedCuHeaderApiVersion={selectedCuHeaderApiVersion}
        analyzerOptions={azureCuAnalyzers}
        analyzersFetchedAt={analyzersFetchedAt}
        isLoadingAnalyzers={isLoadingAnalyzers}
        onEngineChange={setSelectedEngine}
        onTitlePositionChange={setSelectedTitlePosition}
        onHeaderPositionChange={setSelectedHeaderPosition}
        onCuContentsAnalyzerChange={setSelectedCuContentsAnalyzerId}
        onCuContentsApiVersionChange={setSelectedCuContentsApiVersion}
        onCuHeaderAnalyzerChange={setSelectedCuHeaderAnalyzerId}
        onCuHeaderApiVersionChange={setSelectedCuHeaderApiVersion}
        onFetchAnalyzers={handleFetchAnalyzers}
        onPrepare={handlePrepare}
        onExecute={handleExecute}
        preparedPages={preparedPages}
        isLoading={isLoading}
        isPreparing={isPreparing}
        isExecuting={isExecuting}
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
