import { useEffect, useMemo, useState } from "react";
import { BedDouble, LogIn, LogOut, Sparkles, Star, Users, X } from "lucide-react";
import {
  fetchArrivals,
  fetchDepartures,
  fetchInHouseReservations,
  fetchRecommendations,
  generateRecommendations,
  Recommendation,
  Reservation,
} from "../services/api";
import { GuestNameLink } from "./GuestProfilePage";

type TabKey = "in-house" | "arrivals" | "departures";

const TABS: { key: TabKey; label: string; icon: typeof BedDouble; eyebrow: string }[] = [
  { key: "in-house", label: "In-House", icon: BedDouble, eyebrow: "Currently staying" },
  { key: "arrivals", label: "Arrivals", icon: LogIn, eyebrow: "Expected today" },
  { key: "departures", label: "Departures", icon: LogOut, eyebrow: "Checking out today" },
];

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function nightsBetween(a: string, b: string): number {
  const ms = new Date(b).getTime() - new Date(a).getTime();
  return Math.max(0, Math.round(ms / 86400000));
}

function isSameLocalDay(iso: string, ref: Date): boolean {
  const d = new Date(iso);
  return (
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate()
  );
}

type BadgeTone = "gold" | "navy" | "amber" | "muted" | "green";

function Tag({ tone, children }: { tone: BadgeTone; children: React.ReactNode }) {
  const tones: Record<BadgeTone, { bg: string; color: string; border: string }> = {
    gold:  { bg: "rgba(201,169,97,0.14)", color: "#8c7332", border: "rgba(201,169,97,0.45)" },
    navy:  { bg: "rgba(0,30,60,0.08)",    color: "#001E3C", border: "rgba(0,30,60,0.25)" },
    amber: { bg: "rgba(196,128,32,0.13)", color: "#8a5a18", border: "rgba(196,128,32,0.45)" },
    muted: { bg: "rgba(0,0,0,0.04)",      color: "#6b6b6b", border: "rgba(0,0,0,0.15)" },
    green: { bg: "rgba(48,128,72,0.12)",  color: "#286143", border: "rgba(48,128,72,0.4)" },
  };
  const t = tones[tone];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        fontSize: 11,
        letterSpacing: 0.4,
        textTransform: "uppercase",
        background: t.bg,
        color: t.color,
        border: `1px solid ${t.border}`,
        borderRadius: 3,
      }}
    >
      {children}
    </span>
  );
}

/**
 * Map a reservation + current tab to a contextual display badge.
 * Underlying DB status stays the same; this is purely presentation.
 *
 * In-House tab:
 *   CHECKED_IN  — arrival is today (just got here)
 *   DUE_OUT     — departure is today (about to leave)
 *   IN-HOUSE    — staying through today (mid-stay)
 *
 * Arrivals tab:
 *   ARRIVED     — DB says checked_in (and check-in is today)
 *   DUE_OUT     — same-day arrival + departure
 *   DUE_IN      — still pending
 *
 * Departures tab:
 *   DEPARTED    — DB says checked_out
 *   DUE_OUT     — still checked-in, leaving today/soon
 */
function displayBadge(r: Reservation, tab: TabKey): { label: string; tone: BadgeTone } {
  const now = new Date();
  const arrivalToday = isSameLocalDay(r.check_in_date, now);
  const departureToday = isSameLocalDay(r.check_out_date, now);
  const status = (r.status || "").toLowerCase();

  if (tab === "in-house") {
    if (departureToday) return { label: "Due Out", tone: "amber" };
    if (arrivalToday)   return { label: "Checked In", tone: "green" };
    return { label: "In-House", tone: "navy" };
  }

  if (tab === "arrivals") {
    if (status === "checked_in" && arrivalToday && departureToday) {
      return { label: "Due Out", tone: "amber" };
    }
    if (status === "checked_in") return { label: "Arrived", tone: "green" };
    if (arrivalToday && departureToday) return { label: "Due Out", tone: "amber" };
    return { label: "Due In", tone: "gold" };
  }

  // departures tab
  if (status === "checked_out") return { label: "Departed", tone: "muted" };
  return { label: "Due Out", tone: "amber" };
}

export default function ReservationsPage() {
  const [tab, setTab] = useState<TabKey>("in-house");
  const [data, setData] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [recsLoading, setRecsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    setSelectedId(null);   // reset selection when switching tabs
    setRecs(null);
    const fetcher =
      tab === "in-house" ? fetchInHouseReservations :
      tab === "arrivals" ? fetchArrivals : fetchDepartures;
    fetcher()
      .then((rows) => !cancelled && setData(rows))
      .catch((e) => !cancelled && setErr(e?.response?.data?.detail ?? "Failed to load"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [tab]);

  const selected = useMemo(
    () => data.find((r) => r.id === selectedId) || null,
    [data, selectedId]
  );
  const sidePanelOn = tab !== "departures" && selected !== null;

  useEffect(() => {
    if (!selected?.guest_id) { setRecs(null); return; }
    let cancelled = false;
    setRecsLoading(true);
    // Try the freshly-generated recs first; fall back to whatever is saved.
    generateRecommendations(selected.guest_id, 5)
      .catch(() => fetchRecommendations(selected.guest_id))
      .then((rs) => { if (!cancelled) setRecs(rs ?? []); })
      .finally(() => { if (!cancelled) setRecsLoading(false); });
    return () => { cancelled = true; };
  }, [selected?.guest_id]);

  const stats = useMemo(() => {
    const total = data.length;
    const vip = data.filter((r) => r.guest?.vip_status).length;
    const watched = data.filter((r) => r.guest?.is_watched).length;
    return { total, vip, watched };
  }, [data]);

  const active = TABS.find((t) => t.key === tab)!;

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Front desk</div>
        <h1 className="page-h1">Reservations</h1>
        <p className="page-lead">
          Live occupancy view. Switch tabs to see who's currently in-house, who's arriving in the
          next week, and who's heading out.
        </p>
      </header>

      <div
        className="row"
        style={{
          gap: 0,
          borderBottom: "1px solid var(--border-hairline)",
          marginBottom: 18,
        }}
      >
        {TABS.map((t) => {
          const Icon = t.icon;
          const isActive = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              type="button"
              className="btn"
              style={{
                background: "transparent",
                border: "none",
                borderBottom: isActive ? "2px solid var(--color-gold)" : "2px solid transparent",
                borderRadius: 0,
                padding: "10px 18px",
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "var(--color-navy)" : "var(--color-muted)",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <Icon size={14} />
              {t.label}
            </button>
          );
        })}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: sidePanelOn ? "minmax(0, 1fr) 340px" : "minmax(0, 1fr)",
          gap: 18,
          marginBottom: 18,
        }}
      >
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">{active.eyebrow}</div>
              <h3>{active.label}</h3>
            </div>
            <div className="row" style={{ gap: 16 }}>
              <div className="t-caption tnum"><Users size={12} style={{ marginRight: 4, verticalAlign: -1 }} />{stats.total} total</div>
              <div className="t-caption tnum"><Star size={12} style={{ marginRight: 4, verticalAlign: -1 }} />{stats.vip} VIP</div>
            </div>
          </div>
          <div className="panel-body">
            {loading ? (
              <div className="panel-empty">Loading…</div>
            ) : err ? (
              <div className="panel-empty">Error: {err}</div>
            ) : data.length === 0 ? (
              <div className="panel-empty">No reservations to show.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left", fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--color-muted)" }}>
                    <th style={{ padding: "10px 14px" }}>Guest</th>
                    <th style={{ padding: "10px 14px" }}>Room</th>
                    <th style={{ padding: "10px 14px" }}>Check-in</th>
                    <th style={{ padding: "10px 14px" }}>Check-out</th>
                    <th style={{ padding: "10px 14px" }}>Nights</th>
                    <th style={{ padding: "10px 14px" }}>Status</th>
                    <th style={{ padding: "10px 14px" }}>Code</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => {
                    const badge = displayBadge(r, tab);
                    const isSelected = r.id === selectedId;
                    const selectable = tab !== "departures";
                    return (
                      <tr
                        key={r.id}
                        onClick={() => selectable && setSelectedId(isSelected ? null : r.id)}
                        style={{
                          borderTop: "1px solid var(--border-hairline)",
                          background: isSelected ? "rgba(201,169,97,0.08)" : undefined,
                          cursor: selectable ? "pointer" : "default",
                        }}
                      >
                        <td style={{ padding: "12px 14px" }}>
                          {r.guest ? (
                            <GuestNameLink id={r.guest.id} name={r.guest.full_name} />
                          ) : (
                            <span>{`Guest #${r.guest_id}`}</span>
                          )}
                          <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                            {r.guest?.vip_status && <Tag tone="gold">VIP</Tag>}
                            {r.guest?.is_watched && <Tag tone="navy"><Star size={9} style={{ verticalAlign: -1 }} /> Watched</Tag>}
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px" }} className="tnum">{r.room_number ?? "—"}</td>
                        <td style={{ padding: "12px 14px" }}>{fmtDate(r.check_in_date)}</td>
                        <td style={{ padding: "12px 14px" }}>{fmtDate(r.check_out_date)}</td>
                        <td style={{ padding: "12px 14px" }} className="tnum">{nightsBetween(r.check_in_date, r.check_out_date)}</td>
                        <td style={{ padding: "12px 14px" }}><Tag tone={badge.tone}>{badge.label}</Tag></td>
                        <td style={{ padding: "12px 14px", color: "var(--color-muted)", fontSize: 12 }} className="tnum">{r.reservation_code}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {sidePanelOn && selected && (
          <DetailSidePanel
            reservation={selected}
            recs={recs}
            recsLoading={recsLoading}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>

      {tab !== "departures" && !sidePanelOn && data.length > 0 && (
        <div className="t-caption" style={{ color: "var(--color-muted)", marginBottom: 18 }}>
          Click any row to see the guest's notes and personalised recommendations.
        </div>
      )}
    </>
  );
}

function DetailSidePanel({
  reservation,
  recs,
  recsLoading,
  onClose,
}: {
  reservation: Reservation;
  recs: Recommendation[] | null;
  recsLoading: boolean;
  onClose: () => void;
}) {
  const g = reservation.guest;
  return (
    <div className="panel" style={{ alignSelf: "flex-start", position: "sticky", top: 18 }}>
      <div className="panel-head">
        <div>
          <div className="eyebrow">Selected · Room {reservation.room_number ?? "—"}</div>
          <h3 style={{ margin: 0 }}>
            {g ? <GuestNameLink id={g.id} name={g.full_name} /> : `Guest #${reservation.guest_id}`}
          </h3>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onClose}
          aria-label="Close"
          title="Close detail panel"
        >
          <X size={14} />
        </button>
      </div>
      <div className="panel-body padded">
        <div className="t-label" style={{ marginBottom: 4 }}>Special requests</div>
        <div style={{ fontSize: 13, marginBottom: 14, color: reservation.special_requests ? undefined : "var(--color-muted)" }}>
          {reservation.special_requests || "None on this reservation."}
        </div>

        <div className="t-label" style={{ marginBottom: 4 }}>Guest notes</div>
        <div style={{ fontSize: 13, marginBottom: 14, color: g?.notes ? undefined : "var(--color-muted)" }}>
          {g?.notes || "No notes recorded."}
        </div>

        {g?.preferences && (
          <>
            <div className="t-label" style={{ marginBottom: 4 }}>Preferences</div>
            <div style={{ fontSize: 13, marginBottom: 14 }}>{g.preferences}</div>
          </>
        )}

        <div className="t-label" style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 4 }}>
          <Sparkles size={11} /> Suggested for them
        </div>
        {recsLoading ? (
          <div style={{ fontSize: 13, color: "var(--color-muted)" }}>Generating…</div>
        ) : !recs || recs.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--color-muted)" }}>No suggestions available.</div>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {recs.slice(0, 5).map((r) => {
              const svc = r.service;
              const meta = svc
                ? [svc.category, svc.price != null ? `$${svc.price.toFixed(0)}` : null].filter(Boolean).join(" · ")
                : null;
              return (
                <div key={r.id} style={{ padding: 10, border: "1px solid var(--border-hairline)", borderRadius: 4 }}>
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{svc?.name ?? `Service #${r.service_id}`}</div>
                    <div className="t-caption tnum">{(r.score * 100).toFixed(0)}%</div>
                  </div>
                  {meta && <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2 }}>{meta}</div>}
                  {r.reasoning && <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2, fontStyle: "italic" }}>{r.reasoning}</div>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
