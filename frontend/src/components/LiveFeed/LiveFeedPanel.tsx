import { useEffect, useRef, useState } from "react";
import { useWebSocketEvent } from "../../hooks/useWebSocket";

interface DetectionBox {
  track_id: number;
  bbox: [number, number, number, number];
  confidence: number;
  guest_id?: number | null;
  guest_status?: "in_house" | "known_non_guest" | "unknown";
  dwell_seconds?: number;
  is_watched?: boolean;
  is_staff_badge?: boolean;
}

function _fmtDwell(s?: number): string {
  if (!s || s < 0) return "0s";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s - m * 60);
  return `${m}m${r.toString().padStart(2, "0")}`;
}

interface LiveFeedPayload {
  event: "live_feed";
  camera_id: string;
  frame_b64: string;
  detections: DetectionBox[];
  ts: string;
}

interface DetectionUpdatePayload {
  event: "detection_update";
  persons: DetectionBox[];
  faces: [number, number, number, number][];
  tracks: number[];
  ts: string;
}

export default function LiveFeedPanel() {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [fps, setFps] = useState(0);
  const frameTimes = useRef<number[]>([]);

  const { last: liveFeed } = useWebSocketEvent<LiveFeedPayload>("live_feed");
  const { last: detections } = useWebSocketEvent<DetectionUpdatePayload>("detection_update");

  useEffect(() => {
    if (!liveFeed) return;
    const now = performance.now();
    frameTimes.current.push(now);
    frameTimes.current = frameTimes.current.filter((t) => now - t < 5000);
    setFps(frameTimes.current.length / 5);
  }, [liveFeed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = img.clientWidth || canvas.width;
    const h = img.clientHeight || canvas.height;
    canvas.width = w;
    canvas.height = h;
    ctx.clearRect(0, 0, w, h);

    if (!detections?.persons || !img.naturalWidth) return;
    const sx = w / img.naturalWidth;
    const sy = h / img.naturalHeight;

    ctx.font = "10px Manrope";
    detections.persons.forEach((p) => {
      const [x, y, bw, bh] = p.bbox;
      // Color by recognition status (SDD FR-3.3 + staff badge override):
      //   blue   — staff-badged person (alert-exempt, off-duty manager etc.)
      //   red    — watchlisted guest in frame (highest staff priority)
      //   green  — recognized known guest
      //   gold   — unknown / unidentified person
      const isStaff = !!p.is_staff_badge;
      const isWatched = !!p.is_watched && !isStaff;   // staff badge wins
      const isKnown = p.guest_id != null;
      const stroke = isStaff
        ? "#2E6FB8"                                   // calm blue = staff
        : isWatched ? "#C72E2E"
        : isKnown ? "#2E8C5A"
        : "#C9A961";
      const ink = "#00132A";

      // Heavier stroke + outer glow for watched guests so they pop instantly
      ctx.lineWidth = isWatched ? 3 : 1.5;
      if (isWatched) {
        ctx.shadowColor = "rgba(199,46,46,0.55)";
        ctx.shadowBlur = 8;
      }
      ctx.strokeStyle = stroke;
      ctx.strokeRect(x * sx, y * sy, bw * sx, bh * sy);
      ctx.shadowBlur = 0;

      // Label tag — prepend ⚠ for watched, append guest_id/status, append dwell
      const idTag =
        p.guest_id != null ? `G#${p.guest_id}` : `#${p.track_id}`;
      const statusTag =
        p.guest_status === "in_house" ? " · in-house"
        : p.guest_status === "known_non_guest" ? " · known"
        : "";
      const dwellTag = ` · ${_fmtDwell(p.dwell_seconds)}`;
      const label = `${isWatched ? "⚠ " : ""}${idTag}${statusTag}${dwellTag}`;

      const labelW = ctx.measureText(label).width + 10;
      ctx.fillStyle = stroke;
      ctx.fillRect(x * sx, y * sy - 14, labelW, 14);
      ctx.fillStyle = isWatched ? "#fff" : ink;
      ctx.fillText(label, x * sx + 5, y * sy - 4);
    });
  }, [detections, liveFeed]);

  const now = liveFeed?.ts ? new Date(liveFeed.ts).toLocaleTimeString() : "--:--:--";
  const watchedInFrame = (detections?.persons ?? []).filter((p) => p.is_watched).length;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Camera</div>
          <h3>{liveFeed?.camera_id ?? "lobby_main"}</h3>
        </div>
        <div className="right">
          <span className="t-caption tnum">{fps.toFixed(1)} fps</span>
        </div>
      </div>
      <div style={{ padding: 14 }}>
        <div className="feed">
          {liveFeed?.frame_b64 ? (
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${liveFeed.frame_b64}`}
              alt="Live feed"
            />
          ) : (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "grid",
                placeItems: "center",
                color: "rgba(251,248,242,0.5)",
                fontSize: 13,
              }}
            >
              Waiting for camera frames…
            </div>
          )}
          <canvas ref={canvasRef} className="overlay" />

          {watchedInFrame > 0 && (
            <div
              style={{
                position: "absolute",
                top: 12,
                left: 12,
                right: 12,
                padding: "8px 12px",
                background: "rgba(199,46,46,0.92)",
                color: "#fff",
                fontWeight: 600,
                fontSize: 12,
                letterSpacing: 0.8,
                textTransform: "uppercase",
                borderRadius: 3,
                display: "flex",
                alignItems: "center",
                gap: 8,
                boxShadow: "0 4px 14px rgba(199,46,46,0.45)",
                animation: "pulseRed 1.4s ease-in-out infinite",
                pointerEvents: "none",
                zIndex: 4,
              }}
            >
              ⚠ Watchlist match · {watchedInFrame} watched guest{watchedInFrame > 1 ? "s" : ""} in frame
            </div>
          )}

          <div className="feed-overlay-top">
            <span className="feed-cam-label">● LIVE</span>
            <span className="feed-time">{now}</span>
          </div>

          <div className="feed-overlay-bottom">
            <div className="feed-stats">
              <div>
                <div className="v">{detections?.persons?.length ?? 0}</div>
                <div className="l">Persons</div>
              </div>
              <div>
                <div className="v">{detections?.faces?.length ?? 0}</div>
                <div className="l">Faces</div>
              </div>
              <div>
                <div className="v">{detections?.tracks?.length ?? 0}</div>
                <div className="l">Tracks</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
