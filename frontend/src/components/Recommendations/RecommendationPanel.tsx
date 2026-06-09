import { useEffect, useState } from "react";
import { Check, Clock, X } from "lucide-react";
import { useWebSocketEvent } from "../../hooks/useWebSocket";
import {
  fetchRecommendations,
  generateRecommendations,
  Recommendation,
  RecommendationActionStatus,
  setRecommendationStatus,
} from "../../services/api";
import { toast } from "../Toast/Toast";

interface GuestIdentifiedPayload {
  event: "guest_identified";
  guest_id: number;
  name: string;
}

function statusTone(s: string | undefined | null): { bg: string; fg: string; label: string } {
  const v = (s || "").toLowerCase();
  if (v === "accepted") return { bg: "rgba(48,128,72,0.12)",  fg: "#286143", label: "Accepted" };
  if (v === "declined") return { bg: "rgba(199,46,46,0.10)",  fg: "#7a2a2a", label: "Declined" };
  if (v === "presented")return { bg: "rgba(0,30,60,0.08)",    fg: "#001E3C", label: "Deferred" };
  return                       { bg: "rgba(201,169,97,0.14)", fg: "#8c7332", label: "Pending"  };
}

export default function RecommendationPanel() {
  const { last: identified } = useWebSocketEvent<GuestIdentifiedPayload>("guest_identified");
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    if (!identified?.guest_id) return;
    let cancelled = false;
    const id = identified.guest_id;
    setLoading(true);
    generateRecommendations(id, 5)
      .catch(() => fetchRecommendations(id))
      .then((data) => !cancelled && setRecs(data ?? []))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [identified?.guest_id]);

  async function act(rec: Recommendation, status: RecommendationActionStatus) {
    setBusy(rec.id);
    try {
      const updated = await setRecommendationStatus(rec.id, status);
      setRecs((prev) => prev.map((r) => (r.id === rec.id ? { ...r, ...updated } : r)));
      toast.success(`Marked ${status}`, rec.service?.name ?? `Recommendation #${rec.id}`);
    } catch (e: any) {
      toast.error("Couldn't update status", e?.response?.data?.detail ?? "Try again or check the logs.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Upselling</div>
          <h3>Recommendations</h3>
        </div>
      </div>

      {!identified ? (
        <div className="panel-empty">Awaiting an identified guest.</div>
      ) : loading ? (
        <div className="panel-empty">Generating…</div>
      ) : recs.length === 0 ? (
        <div className="panel-empty">No matching services available.</div>
      ) : (
        <div className="panel-body">
          {recs.map((r) => {
            const svc = r.service;
            const label = svc?.name ?? `Service #${r.service_id}`;
            const meta = svc
              ? [svc.category, svc.price != null ? `$${svc.price.toFixed(0)}` : null]
                  .filter(Boolean)
                  .join(" · ")
              : null;
            const tone = statusTone(r.status);
            const isPending = (r.status || "").toLowerCase() === "pending";
            return (
              <div key={r.id} className="rec-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="nm">{label}</div>
                    {meta && <div className="why" style={{ opacity: 0.7 }}>{meta}</div>}
                    {r.reasoning && <div className="why">{r.reasoning}</div>}
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div className="score">{(r.score * 100).toFixed(0)}%</div>
                    <div
                      style={{
                        marginTop: 4, fontSize: 10, padding: "2px 6px", borderRadius: 3,
                        background: tone.bg, color: tone.fg, letterSpacing: 0.4,
                        textTransform: "uppercase", display: "inline-block",
                      }}
                    >
                      {tone.label}
                    </div>
                  </div>
                </div>
                {/* FR-2.8 — Accept / Defer / Decline action row */}
                <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy === r.id || !isPending}
                    onClick={() => act(r, "accepted")}
                    title="Guest accepted this recommendation"
                  >
                    <Check size={12} /> Accept
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy === r.id || !isPending}
                    onClick={() => act(r, "presented")}
                    title="Defer — staff acknowledged, guest hasn't responded yet"
                  >
                    <Clock size={12} /> Defer
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy === r.id || !isPending}
                    onClick={() => act(r, "declined")}
                    title="Guest declined this recommendation"
                  >
                    <X size={12} /> Decline
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
