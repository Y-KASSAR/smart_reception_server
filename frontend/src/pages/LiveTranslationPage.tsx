import { useEffect, useRef, useState } from "react";
import { Languages, Mic, MicOff, Trash2 } from "lucide-react";

interface TranscriptEntry {
  id: number;
  source_lang: string;
  text: string;
  duration_s: number;
  ts: string;
}

const LANG_NAMES: Record<string, string> = {
  en: "English", fr: "French", ar: "Arabic", es: "Spanish", de: "German",
  it: "Italian", ru: "Russian", zh: "Chinese", ja: "Japanese", ko: "Korean",
  tr: "Turkish", hi: "Hindi", pt: "Portuguese", nl: "Dutch", sv: "Swedish",
  fa: "Persian", he: "Hebrew", ur: "Urdu", id: "Indonesian", th: "Thai",
};
const langLabel = (code: string) => LANG_NAMES[code] ?? (code || "?").toUpperCase();

export default function LiveTranslationPage() {
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const nextIdRef = useRef(1);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/translation`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data?.event !== "translation") return;
        const entry: TranscriptEntry = {
          id: nextIdRef.current++,
          source_lang: data.source_lang || "?",
          text: data.text || "",
          duration_s: Number(data.duration_s) || 0,
          ts: data.ts || new Date().toISOString(),
        };
        setEntries((prev) => {
          // Newest first; cap at 200 to avoid unbounded growth
          const next = [entry, ...prev];
          return next.length > 200 ? next.slice(0, 200) : next;
        });
      } catch { /* ignore non-JSON */ }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, []);

  // Auto-scroll the log to top on new entry — entries are newest-first so
  // top is always the latest. (We don't scroll to bottom because most users
  // glance at the freshest line.)
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = 0;
  }, [entries.length]);

  function fmtTime(iso: string): string {
    try { return new Date(iso).toLocaleTimeString(); } catch { return "—"; }
  }

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow"><Languages size={12} style={{ verticalAlign: -1, marginRight: 6 }} />Speech</div>
        <h1 className="page-h1">Live translation</h1>
        <p className="page-lead">
          When this page is open, the lobby microphone is engaged and every
          spoken phrase is transcribed + translated to English in real time.
          Closing the page automatically disengages the pipeline.
        </p>
      </header>

      <div className="row" style={{ gap: 12, marginBottom: 18 }}>
        <span
          className="chip"
          style={{
            background: connected ? "rgba(48,128,72,0.12)" : "rgba(0,0,0,0.05)",
            color: connected ? "#286143" : "#6b6b6b",
          }}
        >
          {connected ? <Mic size={12} style={{ verticalAlign: -1, marginRight: 4 }} /> : <MicOff size={12} style={{ verticalAlign: -1, marginRight: 4 }} />}
          {connected ? "Pipeline engaged" : "Disconnected"}
        </span>
        <span className="t-caption tnum" style={{ color: "var(--color-muted)" }}>
          {entries.length} transcripts captured this session
        </span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setEntries([])}
          disabled={entries.length === 0}
          title="Clear transcript log"
        >
          <Trash2 size={14} /> Clear
        </button>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">Transcript log</div>
            <h3>Most recent first</h3>
          </div>
          <div className="right t-caption" style={{ color: "var(--color-muted)" }}>
            Source language auto-detected · Output: English
          </div>
        </div>
        <div
          ref={logRef}
          className="panel-body"
          style={{ maxHeight: 620, overflowY: "auto" }}
        >
          {entries.length === 0 ? (
            <div className="panel-empty">
              {connected
                ? "Waiting for speech… make sure the Pi's audio_client service is running."
                : "Not connected to the translation pipeline yet."}
            </div>
          ) : (
            entries.map((e) => (
              <div
                key={e.id}
                style={{
                  padding: "14px 18px",
                  borderTop: "1px solid var(--border-hairline)",
                  display: "flex",
                  gap: 16,
                  alignItems: "flex-start",
                }}
              >
                <div style={{ minWidth: 80, flexShrink: 0 }}>
                  <div className="tnum" style={{ fontSize: 12, color: "var(--color-muted)" }}>
                    {fmtTime(e.ts)}
                  </div>
                  <div
                    className="chip"
                    style={{
                      marginTop: 6,
                      background: e.source_lang === "en" ? "rgba(0,30,60,0.06)" : "rgba(201,169,97,0.12)",
                      color: e.source_lang === "en" ? "#001E3C" : "#8c7332",
                      fontSize: 10,
                    }}
                  >
                    {langLabel(e.source_lang)} → EN
                  </div>
                </div>
                <div style={{ flex: 1, fontSize: 15, lineHeight: 1.55, wordBreak: "break-word" }}>
                  {e.text}
                </div>
                <div className="t-caption tnum" style={{ color: "var(--color-muted)", flexShrink: 0 }}>
                  {e.duration_s.toFixed(1)}s
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
