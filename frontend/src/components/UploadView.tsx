import { ChangeEvent, DragEvent, useRef, useState } from "react";
import {
  AzureCuAnalyzer,
  ENGINE_OPTIONS,
  EngineName,
  HEADER_POSITION_OPTIONS,
  HeaderPosition,
  TITLE_POSITION_OPTIONS,
  TitlePosition,
} from "../api";

interface Props {
  selectedEngine: EngineName;
  selectedTitlePosition: TitlePosition;
  selectedHeaderPosition: HeaderPosition;
  selectedCuAnalyzerId: string;
  selectedCuApiVersion: string;
  analyzerOptions: AzureCuAnalyzer[];
  analyzersFetchedAt: string | null;
  isLoadingAnalyzers: boolean;
  onEngineChange: (engine: EngineName) => void;
  onTitlePositionChange: (position: TitlePosition) => void;
  onHeaderPositionChange: (position: HeaderPosition) => void;
  onCuAnalyzerChange: (analyzerId: string) => void;
  onCuApiVersionChange: (apiVersion: string) => void;
  onFetchAnalyzers: () => void;
  onUpload: (
    file: File,
    engine: EngineName,
    titlePosition: TitlePosition,
    headerPosition: HeaderPosition,
  ) => void;
  isLoading: boolean;
}

export default function UploadView({
  selectedEngine,
  selectedTitlePosition,
  selectedHeaderPosition,
  selectedCuAnalyzerId,
  selectedCuApiVersion,
  analyzerOptions,
  analyzersFetchedAt,
  isLoadingAnalyzers,
  onEngineChange,
  onTitlePositionChange,
  onHeaderPositionChange,
  onCuAnalyzerChange,
  onCuApiVersionChange,
  onFetchAnalyzers,
  onUpload,
  isLoading,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isAzureCu = selectedEngine === "azure_cu";

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") {
      onUpload(file, selectedEngine, selectedTitlePosition, selectedHeaderPosition);
    }
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onUpload(file, selectedEngine, selectedTitlePosition, selectedHeaderPosition);
  }

  function handleAnalyzerSelect(value: string) {
    onCuAnalyzerChange(value);
    const found = analyzerOptions.find((a) => a.analyzer_id === value);
    if (found) onCuApiVersionChange(found.api_version);
  }

  return (
    <div style={styles.wrapper}>
      <h1 style={styles.title}>Blueprint Extractor</h1>
      <p style={styles.subtitle}>建築図面PDFからパーツを自動切り出しします</p>

      <div style={styles.grid}>
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>設定</h2>

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

          <div style={{ ...styles.formRow, ...(isAzureCu ? {} : styles.rowDisabled) }}>
            <label htmlFor="cuApiVersion" style={styles.label}>CU API Version</label>
            <input
              id="cuApiVersion"
              value={selectedCuApiVersion}
              onChange={(e) => onCuApiVersionChange(e.target.value)}
              style={styles.input}
              disabled={isLoading || !isAzureCu}
              placeholder="2025-05-01-preview"
            />
          </div>

          <div style={styles.formRow}>
            <label htmlFor="cuAnalyzer" style={styles.label}>Analyzer</label>
            <select
              id="cuAnalyzer"
              value={selectedCuAnalyzerId}
              onChange={(e) => handleAnalyzerSelect(e.target.value)}
              style={styles.select}
              disabled={isLoading || !isAzureCu || analyzerOptions.length === 0}
            >
              <option value="">(未選択)</option>
              {analyzerOptions.map((opt) => (
                <option key={`${opt.analyzer_id}:${opt.api_version}`} value={opt.analyzer_id}>
                  {opt.analyzer_id} ({opt.status})
                </option>
              ))}
            </select>
          </div>

          <div style={styles.actionsRow}>
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
        </section>

        <section style={styles.card}>
          <h2 style={styles.cardTitle}>PDFファイル</h2>
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
                <p>図面を解析中...</p>
              </div>
            ) : (
              <>
                <div style={styles.icon}>📄</div>
                <p style={styles.dropText}>PDFをここにドロップ</p>
                <p style={styles.dropSub}>またはクリックしてファイルを選択</p>
              </>
            )}
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={handleChange}
            disabled={isLoading}
          />
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
    justifyContent: "center",
    minHeight: "100vh",
    padding: "1.5rem",
    background: "#f8fafc",
  },
  title: {
    fontSize: "2rem",
    fontWeight: 700,
    marginBottom: "0.5rem",
  },
  subtitle: {
    color: "#4b5563",
    marginBottom: "1.2rem",
  },
  grid: {
    width: "100%",
    maxWidth: 1100,
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
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
};
