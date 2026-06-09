import { useEffect, useState } from "react";
import { useWebSocketEvent } from "../../hooks/useWebSocket";

/**
 * FR-3.10 — Lobby occupancy map
 *
 * The camera gives us 2D pixel-space bounding boxes per person but no real
 * floor coordinates. We approximate each person's "footprint" by projecting
 * the bottom-center of their bbox into normalised camera-frame space, then
 * rendering that onto a stylised lobby layout. It's not metrically accurate
 * — there's no homography calibration — but it's a useful glanceable
 * "where is everyone in the field of view" view.
 *
 * Color coding mirrors the bbox color scheme (FR-3.3) so the map and the
 * live feed stay visually coherent.
 */

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
interface DetectionUpdatePayload {
  event: "detection_update";
  persons: DetectionBox[];
  faces: number[][];
  tracks: number[];
}
interface LiveFeedPayload {
  event: "live_feed";
  frame_b64: string;
}

// Render area: 320 wide × 220 tall SVG. Camera frame is mapped onto this
// box; doorway/zone overlays drawn in a muted style so the dots pop.
const W = 320;
const H = 220;

function dotColor(p: DetectionBox): string {
  if (p.is_staff_badge) return "#2E6FB8";
  if (p.is_watched)     return "#C72E2E";
  if (p.guest_id != null) return "#2E8C5A";
  return "#C9A961";
}

export default function LobbyMap() {
  const { last: dets } = useWebSocketEvent<DetectionUpdatePayload>("detection_update");
  const { last: feed } = useWebSocketEvent<LiveFeedPayload>("live_feed");

  // Lazily read the natural image size off the most recent frame so we can
  // project pixel bboxes into the SVG. Falls back to a 640×480 assumption
  // if no frame has arrived yet (matches our edge_client default).
  const [imgSize, setImgSize] = useState<{ w: number; h: number }>({ w: 640, h: 480 });
  useEffect(() => {
    if (!feed?.frame_b64) return;
    const img = new Image();
    img.onload = () => setImgSize({ w: img.naturalWidth, h: img.naturalHeight });
    img.src = `data:image/jpeg;base64,${feed.frame_b64}`;
  }, [feed?.frame_b64]);

  const persons = dets?.persons ?? [];

  return (
    <div className="panel" style={{ marginBottom: 20 }}>
      <div className="panel-head">
        <div>
          <div className="eyebrow">Lobby map · FR-3.10</div>
          <h3>Occupancy footprint</h3>
        </div>
        <div className="right t-caption tnum">{persons.length} in view</div>
      </div>
      <div className="panel-body padded" style={{ display: "grid", placeItems: "center" }}>
        <svg
          width="100%"
          viewBox={`0 0 ${W} ${H}`}
          style={{ maxWidth: 520, background: "rgba(0,30,60,0.04)", borderRadius: 6 }}
          aria-label="Approximate lobby occupancy projection"
        >
          {/* Floor outline */}
          <rect x={0.5} y={0.5} width={W - 1} height={H - 1} fill="none"
                stroke="rgba(0,30,60,0.25)" strokeWidth={1} />
          {/* "Camera here" marker at the bottom-center */}
          <g transform={`translate(${W / 2}, ${H - 12})`}>
            <polygon
              points="-8,8 8,8 0,-8"
              fill="rgba(0,30,60,0.55)"
              stroke="rgba(0,30,60,0.7)"
              strokeWidth={1}
            />
            <text x={0} y={22} textAnchor="middle"
                  fontSize={9} fill="rgba(0,30,60,0.7)" fontWeight={500}>
              Camera
            </text>
          </g>
          {/* Camera FOV cone */}
          <polygon
            points={`${W / 2},${H - 16} 12,12 ${W - 12},12`}
            fill="rgba(201,169,97,0.06)"
            stroke="rgba(201,169,97,0.25)"
            strokeDasharray="4 3"
            strokeWidth={1}
          />

          {/* Reception desk band at the top */}
          <rect
            x={W * 0.18} y={10} width={W * 0.64} height={14}
            fill="rgba(0,30,60,0.10)" stroke="rgba(0,30,60,0.20)"
          />
          <text x={W / 2} y={20} textAnchor="middle"
                fontSize={9} fill="rgba(0,30,60,0.55)" fontWeight={500}>
            Reception desk
          </text>

          {/* People dots */}
          {persons.map((p) => {
            const [bx, by, bw, bh] = p.bbox;
            // Project bbox bottom-center into normalised camera space
            const nx = (bx + bw / 2) / Math.max(1, imgSize.w);   // 0..1
            const ny = (by + bh)     / Math.max(1, imgSize.h);   // 0..1
            // Flip vertically: bottom of camera frame = closer to the camera
            // marker at the bottom of the floor plan.
            const px = 14 + nx * (W - 28);
            const py = 28 + (1 - ny) * (H - 56);
            const c = dotColor(p);
            const watched = !!p.is_watched;
            return (
              <g key={p.track_id} transform={`translate(${px}, ${py})`}>
                {watched && (
                  <circle r={11} fill="none" stroke={c} strokeWidth={1.5}
                          strokeDasharray="2 2">
                    <animate attributeName="r" values="9;13;9"
                             dur="1.2s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle r={6} fill={c} stroke="#fff" strokeWidth={1.5} />
                <text x={9} y={3} fontSize={9} fill="rgba(0,30,60,0.85)" fontWeight={500}>
                  {p.guest_id != null ? `G${p.guest_id}` : `#${p.track_id}`}
                </text>
              </g>
            );
          })}

          {persons.length === 0 && (
            <text x={W / 2} y={H / 2} textAnchor="middle"
                  fontSize={11} fill="rgba(0,30,60,0.45)">
              Lobby empty
            </text>
          )}
        </svg>

        <div className="row" style={{ gap: 14, marginTop: 12, fontSize: 11, color: "var(--color-muted)", flexWrap: "wrap" }}>
          <Legend color="#2E6FB8" label="Staff" />
          <Legend color="#C72E2E" label="Watchlist" />
          <Legend color="#2E8C5A" label="Recognised" />
          <Legend color="#C9A961" label="Unknown" />
        </div>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="row" style={{ gap: 5 }}>
      <span style={{
        display: "inline-block", width: 9, height: 9, borderRadius: "50%",
        background: color, border: "1px solid rgba(0,0,0,0.1)",
      }} />
      {label}
    </span>
  );
}
