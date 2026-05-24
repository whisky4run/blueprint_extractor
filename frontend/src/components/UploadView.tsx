import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import {
  AzureCuAnalyzer,
  ENGINE_OPTIONS,
  EngineName,
  HEADER_POSITION_OPTIONS,
  HeaderPosition,
  PageData,
  TITLE_POSITION_OPTIONS,
  TitlePosition,
} from "../api";

interface Props {
  selectedEngine: EngineName;
  selectedTitlePosition: TitlePosition;
  selectedHeaderPosition: HeaderPosition;
  selectedCuContentsAnalyzerId: string;
  selectedCuContentsApiVersion: string;
  selectedCuHeaderAnalyzerId: string;
  selectedCuHeaderApiVersion: string;
  analyzerOptions: AzureCuAnalyzer[];
  analyzersFetchedAt: string | null;
  isLoadingAnalyzers: boolean;
  onEngineChange: (engine: EngineName) => void;
  onTitlePositionChange: (position: TitlePosition) => void;
  onHeaderPositionChange: (position: HeaderPosition) => void;
  onCuContentsAnalyzerChange: (analyzerId: string) => void;
  onCuContentsApiVersionChange: (apiVersion: string) => void;
  onCuHeaderAnalyzerChange: (analyzerId: string) => void;
  onCuHeaderApiVersionChange: (apiVersion: string) => void;
  onFetchAnalyzers: () => void;
  onPrepare: (
    file: File,
    engine: EngineName,
    titlePosition: TitlePosition,
    headerPosition: HeaderPosition,
  ) => void;
  onExecute: () => void;
  preparedPages: PageData[];
  isLoading: boolean;
  isPreparing: boolean;
  isExecuting: boolean;
}

export default function UploadView({
  selectedEngine,
  selectedTitlePosition,
  selectedHeaderPosition,
  selectedCuContentsAnalyzerId,
  selectedCuContentsApiVersion,
  selectedCuHeaderAnalyzerId,
  selectedCuHeaderApiVersion,
  analyzerOptions,
  analyzersFetchedAt,
  isLoadingAnalyzers,
  onEngineChange,
  onTitlePositionChange,
  onHeaderPositionChange,
  onCuContentsAnalyzerChange,
  onCuContentsApiVersionChange,
  onCuHeaderAnalyzerChange,
  onCuHeaderApiVersionChange,
  onFetchAnalyzers,
  onPrepare,
  onExecute,
  preparedPages,
  isLoading,
  isPreparing,
  isExecuting,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [selectedPreparedPage, setSelectedPreparedPage] = useState(0);
  const [debugOpen, setDebugOpen] = useState(true);
  const [isNarrow, setIsNarrow] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < 980;
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const isAzureCu = selectedEngine === "azure_cu";
  const headerAnalyzerOptions = analyzerOptions.filter((a) => a.analyzer_id.toLowerCase().startsWith("bph"));
  const contentsAnalyzerOptions = analyzerOptions.filter((a) =>
    a.analyzer_id.toLowerCase().startsWith("bpc"),
  );

  const hasPreparedPdf = preparedPages.length > 0;
  const isExecuteDisabled =
    isLoading ||
    !hasPreparedPdf ||
    (isAzureCu && (!selectedCuHeaderAnalyzerId || !selectedCuContentsAnalyzerId));

  useEffect(() => {
    if (selectedPreparedPage >= preparedPages.length) {
      setSelectedPreparedPage(0);
    }
  }, [preparedPages.length, selectedPreparedPage]);

  useEffect(() => {
    function onResize() {
      setIsNarrow(window.innerWidth < 980);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") {
      onPrepare(file, selectedEngine, selectedTitlePosition, selectedHeaderPosition);
    }
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onPrepare(file, selectedEngine, selectedTitlePosition, selectedHeaderPosition);
  }

  const currentPreparedPage = preparedPages[selectedPreparedPage];

  function handleContentsAnalyzerSelect(value: string) {
    onCuContentsAnalyzerChange(value);
    const found = analyzerOptions.find((a) => a.analyzer_id === value);
    if (found) onCuContentsApiVersionChange(found.api_version);
  }

  function handleHeaderAnalyzerSelect(value: string) {
    onCuHeaderAnalyzerChange(value);
    const found = analyzerOptions.find((a) => a.analyzer_id === value);
    if (found) onCuHeaderApiVersionChange(found.api_version);
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.topBar}>
        <div>
          <h1 style={styles.title}>Blueprint Extractor</h1>
          <p style={styles.subtitle}>建築図面PDFからパーツを自動切り出しします</p>
        </div>
        <div style={styles.topBarActions}>
          <button
            style={{
              ...styles.btnPrimary,
              ...(isExecuting ? styles.btnBusy : {}),
              ...(isExecuteDisabled ? styles.btnDisabled : {}),
            }}
            type="button"
            disabled={isExecuteDisabled}
            onClick={onExecute}
            title={
              !hasPreparedPdf
                ? "先にPDFを読み込んでください"
                : isAzureCu && (!selectedCuHeaderAnalyzerId || !selectedCuContentsAnalyzerId)
                  ? "ヘッダ用・切り出し候補用のAnalyzerを選択してください"
                  : "現在の設定で解析を実行"
            }
          >
            {isExecuting ? "解析実行中..." : "解析を実行"}
          </button>
          {isExecuting && (
            <span style={styles.runningHint}>
              <span style={styles.dot} />
              AzureCU を実行しています
            </span>
          )}
        </div>
      </div>

      <div
        style={{
          ...styles.grid,
          gridTemplateColumns: isNarrow ? "1fr" : "minmax(0, 3fr) minmax(0, 2fr)",
        }}
      >
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>PDFファイル</h2>
          {!hasPreparedPdf && (
            <div
              style={{
                ...styles.dropzone,
                ...(dragging ? styles.dropzoneDragging : {}),
                ...(isLoading ? styles.dropzoneDisabled : {}),
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => !isLoading && inputRef.current?.click()}
            >
              {isLoading ? (
                <div style={styles.loadingInner}>
                  <div style={styles.spinner} />
                  <p>{isPreparing ? "PDFを読み込み中..." : "解析を実行中..."}</p>
                </div>
              ) : (
                <>
                  <div style={styles.icon}>📄</div>
                  <p style={styles.dropText}>PDFをここにドロップ</p>
                  <p style={styles.dropSub}>またはクリックしてファイルを選択</p>
                </>
              )}
            </div>
          )}

          {hasPreparedPdf && (
            <div style={styles.previewWrap}>
              {preparedPages.length > 1 && (
                <div style={styles.pageTabs}>
                  {preparedPages.map((_, i) => (
                    <button
                      key={i}
                      type="button"
                      style={{
                        ...styles.pageTab,
                        ...(i === selectedPreparedPage ? styles.pageTabActive : {}),
                      }}
                      onClick={() => setSelectedPreparedPage(i)}
                    >
                      ページ {i + 1}
                    </button>
                  ))}
                </div>
              )}
              {currentPreparedPage && (
                <img
                  src={`data:image/png;base64,${currentPreparedPage.data}`}
                  alt={`プレビュー ${selectedPreparedPage + 1}`}
                  style={styles.previewImage}
                />
              )}
              <div style={styles.actionsRow}>
                <button
                  type="button"
                  style={styles.btnSecondary}
                  onClick={() => !isLoading && inputRef.current?.click()}
                  disabled={isLoading}
                >
                  別のPDFを読み込む
                </button>
                {isExecuting && (
                  <span style={styles.runningHint}>
                    <span style={styles.dot} />
                    解析実行中...
                  </span>
                )}
              </div>
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={handleChange}
            disabled={isLoading}
          />
        </section>

        <section style={styles.card}>
          <h2 style={styles.cardTitle}>設定</h2>

          <div style={styles.formRow}>
            <label htmlFor="titlePositionSelect" style={styles.label}>タイトル位置</label>
            <select
              id="titlePositionSelect"
              value={selectedTitlePosition}
              onChange={(e) => onTitlePositionChange(e.target.value as TitlePosition)}
              style={styles.select}
              disabled={isLoading}
            >
              {TITLE_POSITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div style={styles.formRow}>
            <label htmlFor="headerPositionSelect" style={styles.label}>図面ヘッダ位置</label>
            <select
              id="headerPositionSelect"
              value={selectedHeaderPosition}
              onChange={(e) => onHeaderPositionChange(e.target.value as HeaderPosition)}
              style={styles.select}
              disabled={isLoading}
            >
              {HEADER_POSITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* デバッグ設定（アコーディオン） */}
          <div style={styles.debugSection}>
            <button
              type="button"
              style={styles.debugToggle}
              onClick={() => setDebugOpen((v) => !v)}
            >
              <span style={styles.debugToggleArrow}>{debugOpen ? "▼" : "▶"}</span>
              デバッグ設定
            </button>

            {debugOpen && (
              <div style={styles.debugBody}>
                <div style={styles.formRow}>
                  <label htmlFor="engineSelect" style={styles.label}>切り出し方式</label>
                  <select
                    id="engineSelect"
                    value={selectedEngine}
                    onChange={(e) => onEngineChange(e.target.value as EngineName)}
                    style={styles.select}
                    disabled={isLoading}
                  >
                    {ENGINE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ ...styles.formRow, ...(isAzureCu ? {} : styles.rowDisabled) }}>
                  <label htmlFor="cuHeaderAnalyzer" style={styles.label}>ヘッダ用Analyzer</label>
                  <select
                    id="cuHeaderAnalyzer"
                    value={selectedCuHeaderAnalyzerId}
                    onChange={(e) => handleHeaderAnalyzerSelect(e.target.value)}
                    style={styles.select}
                    disabled={isLoading || !isAzureCu || headerAnalyzerOptions.length === 0}
                  >
                    <option value="">(未選択)</option>
                    {headerAnalyzerOptions.map((opt) => (
                      <option key={`${opt.analyzer_id}:${opt.api_version}`} value={opt.analyzer_id}>
                        {opt.analyzer_id} ({opt.status})
                      </option>
                    ))}
                  </select>
                  {selectedCuHeaderApiVersion && (
                    <span style={styles.apiVersionText}>API Version: {selectedCuHeaderApiVersion}</span>
                  )}
                </div>

                <div style={styles.formRow}>
                  <label htmlFor="cuContentsAnalyzer" style={styles.label}>切り出し候補用Analyzer</label>
                  <select
                    id="cuContentsAnalyzer"
                    value={selectedCuContentsAnalyzerId}
                    onChange={(e) => handleContentsAnalyzerSelect(e.target.value)}
                    style={styles.select}
                    disabled={isLoading || !isAzureCu || contentsAnalyzerOptions.length === 0}
                  >
                    <option value="">(未選択)</option>
                    {contentsAnalyzerOptions.map((opt) => (
                      <option key={`${opt.analyzer_id}:${opt.api_version}`} value={opt.analyzer_id}>
                        {opt.analyzer_id} ({opt.status})
                      </option>
                    ))}
                  </select>
                  {selectedCuContentsApiVersion && (
                    <span style={styles.apiVersionText}>API Version: {selectedCuContentsApiVersion}</span>
                  )}
                </div>

                <div style={{ ...styles.actionsRow, ...(isAzureCu ? {} : styles.rowDisabled) }}>
                  <button
                    style={styles.btnSecondary}
                    onClick={onFetchAnalyzers}
                    disabled={isLoading || isLoadingAnalyzers || !isAzureCu}
                    type="button"
                  >
                    {isLoadingAnalyzers ? "取得中..." : "Analyzer一覧を取得"}
                  </button>
                  <span style={styles.metaText}>
                    {analyzersFetchedAt
                      ? `最終取得: ${new Date(analyzersFetchedAt).toLocaleString("ja-JP")}`
                      : "未取得"}
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "flex-start",
    minHeight: "100vh",
    padding: "1.5rem",
    background: "#f8fafc",
  },
  topBar: {
    width: "100%",
    maxWidth: 1200,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "1rem",
    marginBottom: "1rem",
  },
  topBarActions: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    gap: "0.35rem",
  },
  title: {
    fontSize: "2rem",
    fontWeight: 700,
    marginBottom: "0.35rem",
  },
  subtitle: {
    color: "#4b5563",
    marginBottom: 0,
  },
  grid: {
    width: "100%",
    maxWidth: 1200,
    display: "grid",
    gap: "1rem",
  },
  card: {
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 12,
    padding: "1rem",
  },
  cardTitle: {
    fontSize: "1rem",
    fontWeight: 700,
    marginBottom: "0.9rem",
    color: "#374151",
  },
  formRow: {
    display: "flex",
    flexDirection: "column",
    gap: "0.35rem",
    marginBottom: "0.8rem",
  },
  rowDisabled: {
    opacity: 0.6,
  },
  label: {
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "#4b5563",
  },
  select: {
    border: "1px solid #d1d5db",
    borderRadius: 8,
    padding: "0.45rem 0.6rem",
    fontSize: "0.9rem",
    background: "#fff",
  },
  input: {
    border: "1px solid #d1d5db",
    borderRadius: 8,
    padding: "0.45rem 0.6rem",
    fontSize: "0.9rem",
    background: "#fff",
  },
  actionsRow: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    flexWrap: "wrap",
  },
  btnSecondary: {
    background: "#fff",
    color: "#374151",
    border: "1px solid #d1d5db",
    borderRadius: 8,
    padding: "0.45rem 0.9rem",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  btnPrimary: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "0.45rem 0.9rem",
    fontSize: "0.85rem",
    fontWeight: 700,
  },
  btnBusy: {
    opacity: 0.85,
  },
  btnDisabled: {
    opacity: 0.45,
    cursor: "not-allowed",
  },
  runningHint: {
    display: "inline-flex",
    alignItems: "center",
    gap: "0.35rem",
    fontSize: "0.8rem",
    color: "#1d4ed8",
    fontWeight: 600,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    background: "#2563eb",
    display: "inline-block",
  },
  metaText: {
    fontSize: "0.78rem",
    color: "#6b7280",
  },
  dropzone: {
    width: "100%",
    minHeight: 300,
    border: "2px dashed #aaa",
    borderRadius: 12,
    padding: "2rem 1.5rem",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.75rem",
    background: "#fff",
    cursor: "pointer",
    transition: "border-color 0.15s, background 0.15s",
  },
  dropzoneDragging: {
    borderColor: "#2563eb",
    background: "#eff6ff",
  },
  dropzoneDisabled: {
    cursor: "not-allowed",
    opacity: 0.6,
  },
  icon: {
    fontSize: "3rem",
  },
  dropText: {
    fontWeight: 600,
    fontSize: "1.1rem",
  },
  dropSub: {
    color: "#888",
    fontSize: "0.9rem",
  },
  loadingInner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "1rem",
  },
  spinner: {
    width: 40,
    height: 40,
    border: "4px solid #e2e8f0",
    borderTop: "4px solid #2563eb",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  previewWrap: {
    display: "flex",
    flexDirection: "column",
    gap: "0.6rem",
  },
  previewImage: {
    width: "100%",
    border: "1px solid #d1d5db",
    borderRadius: 8,
    background: "#fff",
  },
  pageTabs: {
    display: "flex",
    gap: "0.4rem",
    flexWrap: "wrap",
  },
  pageTab: {
    border: "1px solid #d1d5db",
    background: "#fff",
    color: "#374151",
    borderRadius: 6,
    padding: "0.2rem 0.55rem",
    fontSize: "0.8rem",
    cursor: "pointer",
  },
  pageTabActive: {
    background: "#dbeafe",
    borderColor: "#93c5fd",
    color: "#1d4ed8",
  },
  debugSection: {
    marginTop: "0.4rem",
    borderTop: "1px solid #e5e7eb",
    paddingTop: "0.6rem",
  },
  debugToggle: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    background: "none",
    border: "none",
    padding: "0.2rem 0",
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "#6b7280",
    cursor: "pointer",
    width: "100%",
    textAlign: "left",
  },
  debugToggleArrow: {
    fontSize: "0.7rem",
    color: "#9ca3af",
  },
  debugBody: {
    marginTop: "0.75rem",
  },
  apiVersionText: {
    fontSize: "0.75rem",
    color: "#9ca3af",
    marginTop: "0.15rem",
  },
};
