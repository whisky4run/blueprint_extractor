import { useRef, useState, DragEvent, ChangeEvent } from "react";

interface Props {
  onUpload: (file: File) => void;
  isLoading: boolean;
}

export default function UploadView({ onUpload, isLoading }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") onUpload(file);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  }

  return (
    <div style={styles.wrapper}>
      <h1 style={styles.title}>Blueprint Extractor</h1>
      <p style={styles.subtitle}>建築図面PDFからパーツを自動切り出しします</p>

      <div
        style={{
          ...styles.dropzone,
          ...(dragging ? styles.dropzoneDragging : {}),
          ...(isLoading ? styles.dropzoneDisabled : {}),
        }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
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
    padding: "2rem",
  },
  title: {
    fontSize: "2rem",
    fontWeight: 700,
    marginBottom: "0.5rem",
  },
  subtitle: {
    color: "#666",
    marginBottom: "2.5rem",
  },
  dropzone: {
    width: "100%",
    maxWidth: 480,
    border: "2px dashed #aaa",
    borderRadius: 12,
    padding: "3rem 2rem",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
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
