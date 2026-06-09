import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { wsClient } from "../../services/websocket";
import { fetchGuest, Guest } from "../../services/api";

interface GuestIdentifiedPayload {
  event: "guest_identified";
  guest_id: number;
  name: string;
  confidence: number;
  ts: string;
}

interface VisibleGuest {
  guest: Guest;
  confidence: number;       // most recent reported match score
  bestConfidence: number;   // highest seen this session
  firstSeenTs: number;      // performance.now() when first added
  lastSeenTs: number;       // performance.now() of most recent event
}

// A guest is considered "currently in frame" if we've seen a guest_identified
// event for them in the last N seconds. Recognition runs every Nth frame so a
// brief detection gap shouldn't drop the card immediately.
const VISIBLE_TTL_MS = 10_000;

// Cap how many cards we render at once so the page can't be flooded by a
// passing crowd. Older cards are kept in state (for stable identity) but
// scrolled out of view.
const MAX_VISIBLE_CARDS = 6;

function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

export default function GuestInfoPanel() {
  const [visible, setVisible] = useState<Map<number, VisibleGuest>>(new Map());
  const [connected, setConnected] = useState(false);
  const fetchedRef = useRef<Set<number>>(new Set());      // dedupe inflight + cached fetches
  const [, forceTick] = useState(0);                       // re-render every second for TTL pruning

  useEffect(() => {
    const offStatus = wsClient.onStatus(setConnected);

    const offEvent = wsClient.on("guest_identified", (raw) => {
      const ev = raw as GuestIdentifiedPayload;
      if (!ev?.guest_id) return;
      const now = performance.now();
      const gid = ev.guest_id;

      setVisible((prev) => {
        const next = new Map(prev);
        const existing = next.get(gid);
        if (existing) {
          next.set(gid, {
            ...existing,
            confidence: ev.confidence,
            bestConfidence: Math.max(existing.bestConfidence, ev.confidence),
            lastSeenTs: now,
          });
          return next;
        }
        // First sighting — placeholder until fetchGuest resolves
        next.set(gid, {
          guest: { id: gid, full_name: ev.name || `Guest #${gid}` } as Guest,
          confidence: ev.confidence,
          bestConfidence: ev.confidence,
          firstSeenTs: now,
          lastSeenTs: now,
        });
        return next;
      });

      // Fetch real guest profile once per guest_id
      if (!fetchedRef.current.has(gid)) {
        fetchedRef.current.add(gid);
        fetchGuest(gid)
          .then((g) => {
            setVisible((prev) => {
              const next = new Map(prev);
              const cur = next.get(gid);
              if (!cur) return prev;
              next.set(gid, { ...cur, guest: g });
              return next;
            });
          })
          .catch(() => {
            // Leave the placeholder; allow re-fetch on a later sighting
            fetchedRef.current.delete(gid);
          });
      }
    });

    return () => { offEvent(); offStatus(); };
  }, []);

  // TTL pruner: every 1s, drop entries that haven't been re-sighted in a while
  useEffect(() => {
    const interval = window.setInterval(() => {
      const now = performance.now();
      setVisible((prev) => {
        let changed = false;
        const next = new Map<number, VisibleGuest>();
        prev.forEach((v, k) => {
          if (now - v.lastSeenTs < VISIBLE_TTL_MS) {
            next.set(k, v);
          } else {
            changed = true;
            fetchedRef.current.delete(k);
          }
        });
        return changed ? next : prev;
      });
      forceTick((t) => t + 1); // tick for "X seconds ago" labels
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  const list = Array.from(visible.values())
    .sort((a, b) => b.lastSeenTs - a.lastSeenTs)
    .slice(0, MAX_VISIBLE_CARDS);

  const stale = list.filter((v) => performance.now() - v.lastSeenTs > 3000).length;
  const fresh = list.length - stale;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Recognised</div>
          <h3>Guest profiles · {list.length}</h3>
        </div>
        <div className="right">
          {list.length > 0 ? (
            <span className="t-caption tnum">
              {fresh} live · {stale} fading
            </span>
          ) : (
            <span className="t-caption" style={{ color: "var(--color-muted)" }}>
              {connected ? "Waiting for a match…" : "Offline"}
            </span>
          )}
        </div>
      </div>

      {list.length === 0 ? (
        <div className="empty">
          <div className="h">No guest identified yet</div>
          <div className="s">Profiles appear here the moment someone is recognised.</div>
        </div>
      ) : (
        <div
          className="panel-body"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 0,
            maxHeight: 560,
            overflowY: "auto",
          }}
        >
          {list.map((v) => (
            <GuestCard key={v.guest.id} entry={v} />
          ))}
        </div>
      )}
    </div>
  );
}

function GuestCard({ entry }: { entry: VisibleGuest }) {
  const g = entry.guest;
  const ageMs = performance.now() - entry.lastSeenTs;
  const isFading = ageMs > 3000; // not seen for 3+ seconds = de-emphasize
  const opacity = isFading ? 0.55 : 1;
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        padding: "12px 14px",
        borderTop: "1px solid var(--border-hairline)",
        opacity,
        transition: "opacity 0.3s ease",
        alignItems: "flex-start",
      }}
    >
      <div className={`av${g.vip_status ? " vip" : ""}`}>{initials(g.full_name)}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Link
          to={`/guests/${g.id}`}
          style={{ color: "inherit", textDecoration: "none" }}
          title="Open full profile"
        >
          <div
            style={{
              fontWeight: 500,
              fontSize: 15,
              borderBottom: "1px dashed var(--border-hairline)",
              display: "inline-block",
            }}
          >
            {g.full_name}
            <ExternalLink size={11} style={{ verticalAlign: -1, marginLeft: 6, opacity: 0.6 }} />
          </div>
        </Link>
        <div className="row" style={{ gap: 6, marginTop: 4 }}>
          {g.vip_status && (<span className="chip vip"><span className="d" />VIP</span>)}
          {g.is_watched && (
            <span className="chip" style={{ color: "#001E3C", background: "rgba(0,30,60,0.08)" }}>
              <span className="d" />Watched
            </span>
          )}
          {g.status && (<span className="chip neutral"><span className="d" />{g.status}</span>)}
        </div>
        {g.is_watched && g.watch_reason && (
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: "var(--color-security-fg, #7a2a2a)",
              fontStyle: "italic",
            }}
          >
            ⚠ {g.watch_reason}
          </div>
        )}
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div className="tnum" style={{ fontSize: 13, fontWeight: 500 }}>
          {(entry.confidence * 100).toFixed(1)}%
        </div>
        <div className="t-caption" style={{ color: "var(--color-muted)", fontSize: 11, marginTop: 2 }}>
          {isFading ? `${Math.round(ageMs / 1000)}s ago` : "live"}
        </div>
      </div>
    </div>
  );
}
