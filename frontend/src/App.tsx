import { useState } from "react";
import { DetectedPart, PageData, downloadUrl, getPreview, uploadPdf } from "./api";
import PreviewView from "./components/PreviewView";
import UploadView from "./components/UploadView";

type AppState =
  | { screen: "upload" }
  | { screen: "preview"; sessionId: string; pages: PageData[]; parts: DetectedPart[] };

export default function App() {
  const [state, setState] = useState<AppState>({ screen: "upload" });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setIsLoading(true);
    setError(null);
    try {
      const { session_id } = await uploadPdf(file);
      const preview = await getPreview(session_id);
      setState({
        screen: "preview",
        sessionId: session_id,
        pages: preview.pages,
        parts: preview.parts,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラーが発生しました");
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
        onDownload={handleDownload}
        onReset={handleReset}
      />
    );
  }

  return (
    <>
      <UploadView onUpload={handleUpload} isLoading={isLoading} />
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
