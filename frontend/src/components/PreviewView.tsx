import { useEffect, useRef, useState } from "react";
import { DetectedPart, PageData } from "../api";

interface Props {
  sessionId: string;
  pages: PageData[];
  parts: DetectedPart[];
  onDownload: () => void;
  onReset: () => void;
}

export default function PreviewView({ sessionId, pages, parts, onDownload, onReset }: Props) {
  const [selectedPage, setSelectedPage] = useState(0);
  const [imageSize, setImageSize] = useState<{ w: number; h: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const currentPage = pages[selectedPage];
  const currentParts = parts.filter((p) => p.page === selectedPage);

  useEffect(() => {
    setImageSize(null);
  }, [selectedPage]);

  function handleImageLoad() {
    if (imgRef.current) {
      setImageSize({ w: imgRef.current.clientWidth, h: imgRef.current.clientHeight });
    }
  }

  function overlayStyle(part: DetectedPart, naturalW: number, naturalH: number): React.CSSProperties {
    if (!imageSize) return {};
    const scaleX = imageSize.w / naturalW;
    const scaleY = imageSize.h / naturalH;

    return {
      position: "absolute",
      left: part.bbox.x * scaleX,
      top: part.bbox.y * scaleY,
      width: part.bbox.w * scaleX,
      height: part.bbox.h * scaleY,
      border: "2px solid #ef4444",
      boxSizing: "border-box",
      pointerEvents: "none",
    };
  }

  function labelStyle(part: DetectedPart, naturalW: number, naturalH: number): React.CSSProperties {
    if (!imageSize) return {};
    const scaleX = imageSize.w / naturalW;
    const scaleY = imageSize.h / naturalH;

    return {
      position: "absolute",
      left: part.bbox.x * scaleX,
      top: Math.max(0, part.bbox.y * scaleY - 22),
      background: "#ef4444",
      color: "#fff",
      fontSize: 11,
      padding: "1px 4px",
      borderRadius: 3,
      whiteSpace: "nowrap",
      maxWidth: 200,
      overflow: "hidden",
      textOverflow: "ellipsis",
      pointerEvents: "none",
    };
  }

  const naturalW = imgRef.current?.naturalWidth ?? 1;
  const naturalH = imgRef.current?.naturalHeight ?? 1;

  return (
    <div style={styles.wrapper}>
      <header style={styles.header}>
        <h1 style={styles.title}>Blueprint Extractor</h1>
        <div style={styles.headerActions}>
          <span style={styles.badge}>{parts.length} パーツ検出</span>
          <button style={styles.btnSecondary} onClick={onReset}>
            別のPDFを開く
          </button>
          <button style={styles.btnPrimary} onClick={onDownload}>
            PNG一括ダウンロード
          </button>
        </div>
      </header>

      <div style={styles.body}>
        {pages.length > 1 && (
          <div style={styles.pageTabs}>
            {pages.map((_, i) => (
              <button
                key={i}
                style={{
                  ...styles.pageTab,
                  ...(i === selectedPage ? styles.pageTabActive : {}),
                }}
                onClick={() => setSelectedPage(i)}
              >
                ページ {i + 1}
              </button>
            ))}
          </div>
        )}

        <div style={styles.canvas}>
          <div style={{ position: "relative", display: "inline-block" }}>
            <img
              ref={imgRef}
              src={`data:image/png;base64,${currentPage.data}`}
              alt={`ページ ${selectedPage + 1}`}
              style={styles.pageImage}
              onLoad={handleImageLoad}
            />
            {imageSize &&
              currentParts.map((part, i) => (
                <div key={i}>
                  <div style={overlayStyle(part, naturalW, naturalH)} />
                  <div style={labelStyle(part, naturalW, naturalH)}>{part.title}</div>
                </div>
              ))}
          </div>
        </div>

        <aside style={styles.sidebar}>
          <h2 style={styles.sidebarTitle}>検出パーツ一覧</h2>
          {parts.length === 0 ? (
            <p style={styles.noPartsText}>パーツが検出されませんでした</p>
          ) : (
            <ul style={styles.partsList}>
              {parts.map((part, i) => (
                <li
                  key={i}
                  style={{
                    ...styles.partItem,
                    ...(part.page === selectedPage ? styles.partItemActive : {}),
                  }}
                  onClick={() => setSelectedPage(part.page)}
                >
                  <span style={styles.partTitle}>{part.title}</span>
                  {pages.length > 1 && (
                    <span style={styles.partPage}>P{part.page + 1}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100vh",
    background: "#f5f5f5",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.75rem 1.5rem",
    background: "#fff",
    borderBottom: "1px solid #e5e7eb",
    gap: "1rem",
    flexWrap: "wrap",
  },
  title: {
    fontSize: "1.25rem",
    fontWeight: 700,
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    flexWrap: "wrap",
  },
  badge: {
    background: "#dbeafe",
    color: "#1d4ed8",
    borderRadius: 9999,
    padding: "0.2rem 0.75rem",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
  btnPrimary: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "0.5rem 1.25rem",
    fontWeight: 600,
    fontSize: "0.9rem",
  },
  btnSecondary: {
    background: "#fff",
    color: "#374151",
    border: "1px solid #d1d5db",
    borderRadius: 8,
    padding: "0.5rem 1rem",
    fontSize: "0.9rem",
  },
  body: {
    display: "grid",
    gridTemplateColumns: "1fr 240px",
    gridTemplateRows: "auto 1fr",
    flex: 1,
    overflow: "hidden",
  },
  pageTabs: {
    gridColumn: "1 / -1",
    display: "flex",
    gap: "0.5rem",
    padding: "0.75rem 1rem",
    background: "#fff",
    borderBottom: "1px solid #e5e7eb",
  },
  pageTab: {
    padding: "0.3rem 0.9rem",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#fff",
    fontSize: "0.85rem",
  },
  pageTabActive: {
    background: "#2563eb",
    color: "#fff",
    border: "1px solid #2563eb",
  },
  canvas: {
    padding: "1rem",
    overflow: "auto",
    background: "#e5e7eb",
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
  },
  pageImage: {
    maxWidth: "100%",
    display: "block",
    boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
  },
  sidebar: {
    background: "#fff",
    borderLeft: "1px solid #e5e7eb",
    padding: "1rem",
    overflow: "auto",
  },
  sidebarTitle: {
    fontSize: "0.9rem",
    fontWeight: 700,
    marginBottom: "0.75rem",
    color: "#374151",
  },
  noPartsText: {
    color: "#9ca3af",
    fontSize: "0.85rem",
  },
  partsList: {
    listStyle: "none",
    display: "flex",
    flexDirection: "column",
    gap: "0.25rem",
  },
  partItem: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.4rem 0.6rem",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.82rem",
    gap: "0.5rem",
  },
  partItemActive: {
    background: "#eff6ff",
    color: "#1d4ed8",
  },
  partTitle: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  partPage: {
    flexShrink: 0,
    color: "#9ca3af",
    fontSize: "0.75rem",
  },
};
