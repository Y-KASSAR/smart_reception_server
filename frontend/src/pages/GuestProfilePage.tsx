import { ChangeEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Camera, Crown, Eye, EyeOff, FileImage, IdCard, Mail, Phone, Globe,
  FileText, BedDouble, ClipboardList, Shield, ShieldOff, Sparkles, Upload, DollarSign,
  Trash2, ScanFace,
} from "lucide-react";
import {
  currentRole,
  deleteGuestEmbedding,
  embedFaceForGuest,
  fetchGuestEmbeddings,
  fetchGuestSummary,
  GuestEmbedding,
  GuestSummary,
  setGuestWatchlist,
  setStaffBadge,
} from "../services/api";
import { useWebSocketEvent } from "../hooks/useWebSocket";

interface LiveFeedPayload { event: "live_feed"; frame_b64: string; ts: string; }

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fmtMoney(n: number, currency = "USD"): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `$${n.toFixed(0)}`;
  }
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{
      border: "1px solid var(--border-hairline)",
      padding: "14px 18px",
      borderRadius: 4,
      background: "var(--bg-canvas)",
    }}>
      <div style={{ fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--color-muted)" }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 500, marginTop: 4 }} className="tnum">{value}</div>
      {sub && <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function KV({ icon: Icon, k, v, mono = false }:
  { icon?: any; k: string; v: string | null | undefined; mono?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderBottom: "1px solid var(--border-hairline)" }}>
      {Icon && <Icon size={14} style={{ marginTop: 3, color: "var(--color-muted)", flexShrink: 0 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--color-muted)" }}>{k}</div>
        <div className={mono ? "tnum" : ""} style={{ fontSize: 14, marginTop: 2, wordBreak: "break-word" }}>
          {v || "—"}
        </div>
      </div>
    </div>
  );
}

function StatusTag({ status }: { status: string | null }) {
  const s = (status || "").toLowerCase();
  const map: Record<string, { bg: string; color: string; label: string }> = {
    checked_in:  { bg: "rgba(48,128,72,0.12)",  color: "#286143", label: "Checked-In" },
    confirmed:   { bg: "rgba(201,169,97,0.14)", color: "#8c7332", label: "Confirmed" },
    due_in:      { bg: "rgba(201,169,97,0.14)", color: "#8c7332", label: "Due In" },
    due_out:     { bg: "rgba(196,128,32,0.13)", color: "#8a5a18", label: "Due Out" },
    checked_out: { bg: "rgba(0,0,0,0.05)",       color: "#6b6b6b", label: "Departed" },
    cancelled:   { bg: "rgba(0,0,0,0.05)",       color: "#6b6b6b", label: "Cancelled" },
    noshow:      { bg: "rgba(120,30,30,0.10)",  color: "#7a2a2a", label: "No-Show" },
    pending:     { bg: "rgba(201,169,97,0.14)", color: "#8c7332", label: "Pending" },
    presented:   { bg: "rgba(0,30,60,0.08)",    color: "#001E3C", label: "Presented" },
    accepted:    { bg: "rgba(48,128,72,0.12)",  color: "#286143", label: "Accepted" },
    declined:    { bg: "rgba(120,30,30,0.10)",  color: "#7a2a2a", label: "Declined" },
  };
  const t = map[s] || { bg: "rgba(0,0,0,0.04)", color: "#6b6b6b", label: s || "—" };
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", fontSize: 11,
      letterSpacing: 0.4, textTransform: "uppercase",
      background: t.bg, color: t.color, borderRadius: 3,
    }}>{t.label}</span>
  );
}

export default function GuestProfilePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const guestId = Number(id);

  const [data, setData] = useState<GuestSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyWatch, setBusyWatch] = useState(false);
  const [busyBadge, setBusyBadge] = useState(false);
  const isAdmin = currentRole() === "admin";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    fetchGuestSummary(guestId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setErr(e?.response?.data?.detail ?? "Failed to load"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [guestId]);

  if (loading) return <div className="page-empty">Loading…</div>;
  if (err) return <div className="page-empty">Error: {err}</div>;
  if (!data) return null;

  const g = data.guest;

  async function toggleWatch() {
    if (busyWatch) return;
    if (!g.is_watched) {
      const reason = window.prompt(
        `Add ${g.full_name} to the watchlist. Reason shown to staff in the alert (optional):`,
        ""
      );
      if (reason === null) return;
      setBusyWatch(true);
      try {
        const u = await setGuestWatchlist(g.id, true, reason || undefined);
        setData((prev) => prev ? { ...prev, guest: { ...prev.guest, is_watched: u.is_watched, watch_reason: u.watch_reason } } : prev);
      } finally { setBusyWatch(false); }
    } else {
      setBusyWatch(true);
      try {
        const u = await setGuestWatchlist(g.id, false);
        setData((prev) => prev ? { ...prev, guest: { ...prev.guest, is_watched: u.is_watched, watch_reason: u.watch_reason } } : prev);
      } finally { setBusyWatch(false); }
    }
  }

  async function toggleStaffBadge() {
    if (busyBadge || !isAdmin) return;
    if (!g.is_staff_badge) {
      const label = window.prompt(
        `Issue a staff badge to ${g.full_name}? While active, this person triggers NO alerts (security/assistance/VIP/wanted). Optional label (e.g. "Floor Manager - John"):`,
        ""
      );
      if (label === null) return;
      setBusyBadge(true);
      try {
        const u = await setStaffBadge(g.id, true, label || undefined);
        setData((prev) => prev ? { ...prev, guest: { ...prev.guest, is_staff_badge: u.is_staff_badge, staff_badge_label: u.staff_badge_label } } : prev);
      } catch (e: any) {
        alert(e?.response?.data?.detail ?? "Failed to set badge (admin role required).");
      } finally { setBusyBadge(false); }
    } else {
      if (!window.confirm(`Remove staff badge from ${g.full_name}? Alerts will resume firing for them.`)) return;
      setBusyBadge(true);
      try {
        const u = await setStaffBadge(g.id, false);
        setData((prev) => prev ? { ...prev, guest: { ...prev.guest, is_staff_badge: u.is_staff_badge, staff_badge_label: u.staff_badge_label } } : prev);
      } finally { setBusyBadge(false); }
    }
  }

  return (
    <>
      <header className="page-head">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <button
              onClick={() => navigate(-1)}
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ marginBottom: 10 }}
            >
              <ArrowLeft size={14} /> Back
            </button>
            <div className="page-eyebrow">Guest profile · #{g.id}</div>
            <h1 className="page-h1" style={{ marginTop: 6 }}>
              {g.full_name}
              {g.vip_status && (
                <Crown size={20} color="var(--color-gold-600)" style={{ marginLeft: 10, verticalAlign: -3 }} />
              )}
            </h1>
            <div className="row" style={{ gap: 8, marginTop: 6 }}>
              <StatusTag status={g.status} />
              {g.vip_status && <span className="chip vip"><span className="d" />VIP</span>}
              {g.is_watched && (
                <span className="chip" style={{ color: "#001E3C", background: "rgba(0,30,60,0.08)" }}>
                  <span className="d" />Watched
                </span>
              )}
              {g.is_staff_badge && (
                <span className="chip" style={{ color: "#286143", background: "rgba(48,128,72,0.12)" }}>
                  <span className="d" />Staff badge{g.staff_badge_label ? ` · ${g.staff_badge_label}` : ""}
                </span>
              )}
            </div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            {isAdmin && (
              <button
                type="button"
                className={`btn ${g.is_staff_badge ? "btn-ghost" : "btn-primary"}`}
                disabled={busyBadge}
                onClick={toggleStaffBadge}
                title="Admin only — suppresses ALL alerts for this person"
              >
                {g.is_staff_badge ? <ShieldOff size={14} /> : <Shield size={14} />}
                {g.is_staff_badge ? "Revoke staff badge" : "Issue staff badge"}
              </button>
            )}
            <button
              type="button"
              className={`btn ${g.is_watched ? "btn-ghost" : "btn-gold"}`}
              disabled={busyWatch}
              onClick={toggleWatch}
            >
              {g.is_watched ? <EyeOff size={14} /> : <Eye size={14} />}
              {g.is_watched ? "Remove from watchlist" : "Add to watchlist"}
            </button>
          </div>
        </div>
      </header>

      {/* Stat strip */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20,
      }}>
        <StatCard label="Total stays" value={String(data.stays.total)}
          sub={`${data.stays.active} active · ${data.stays.completed} completed`} />
        <StatCard label="Lobby visits" value={String(data.visits.total)} />
        <StatCard label="Recommendations"
          value={`${data.recommendations.accepted} / ${data.recommendations.total}`}
          sub={`accepted · ${data.recommendations.declined} declined`} />
        <StatCard label="Total billed"
          value={fmtMoney(data.finance.total_billed, data.finance.currency)}
          sub={`avg ${fmtMoney(data.finance.avg_per_stay, data.finance.currency)} / stay`} />
      </div>

      <div className="grid-2col">
        {/* Profile + contact + documents */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Identity</div>
              <h3>Contact & document</h3>
            </div>
          </div>
          <div className="panel-body padded">
            <KV icon={Mail}  k="Email" v={g.email} />
            <KV icon={Phone} k="Phone" v={g.phone} mono />
            <KV icon={Globe} k="Nationality" v={g.nationality} />
            <KV icon={IdCard} k="ID type" v={g.id_type ? g.id_type.replace(/_/g, " ") : null} />
            <KV icon={IdCard} k="ID number" v={g.id_number} mono />
            <KV icon={FileText} k="Language" v={g.language_preference?.toUpperCase()} />
            {g.is_watched && g.watch_reason && (
              <div style={{ marginTop: 12, padding: 10, background: "var(--color-assistance-bg)", border: "1px solid var(--color-assistance-tint)", borderRadius: 4, fontSize: 13 }}>
                <strong>Watch reason:</strong> {g.watch_reason}
              </div>
            )}
          </div>
        </div>

        {/* Preferences + notes + past requests */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Personalisation</div>
              <h3>Preferences, notes & history</h3>
            </div>
          </div>
          <div className="panel-body padded">
            <div className="t-label" style={{ marginBottom: 4 }}>Preferences</div>
            <div style={{ fontSize: 14, marginBottom: 14, color: g.preferences ? undefined : "var(--color-muted)" }}>
              {g.preferences || "No preferences recorded."}
            </div>
            <div className="t-label" style={{ marginBottom: 4 }}>General notes</div>
            <div style={{ fontSize: 14, marginBottom: 14, color: g.notes ? undefined : "var(--color-muted)" }}>
              {g.notes || "No notes."}
            </div>
            <div className="t-label" style={{ marginBottom: 4 }}>Previous requests</div>
            {data.special_requests_history.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--color-muted)" }}>No special requests on past reservations.</div>
            ) : (
              <ul style={{ paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
                {data.special_requests_history.map((req, i) => <li key={i}>{req}</li>)}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Stays history */}
      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <div>
            <div className="eyebrow"><BedDouble size={12} style={{ verticalAlign: -1, marginRight: 4 }} />Stays</div>
            <h3>Reservations history</h3>
          </div>
        </div>
        <div className="panel-body">
          {data.stays.items.length === 0 ? (
            <div className="panel-empty">No reservations on record.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--color-muted)" }}>
                  <th style={{ padding: "10px 14px" }}>Code</th>
                  <th style={{ padding: "10px 14px" }}>Room</th>
                  <th style={{ padding: "10px 14px" }}>Check-in</th>
                  <th style={{ padding: "10px 14px" }}>Check-out</th>
                  <th style={{ padding: "10px 14px" }}>Status</th>
                  <th style={{ padding: "10px 14px", textAlign: "right" }}>Billed</th>
                </tr>
              </thead>
              <tbody>
                {data.stays.items.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--border-hairline)" }}>
                    <td style={{ padding: "10px 14px" }} className="tnum">{s.reservation_code}</td>
                    <td style={{ padding: "10px 14px" }} className="tnum">{s.room_number ?? "—"}</td>
                    <td style={{ padding: "10px 14px" }}>{fmtDate(s.check_in_date)}</td>
                    <td style={{ padding: "10px 14px" }}>{fmtDate(s.check_out_date)}</td>
                    <td style={{ padding: "10px 14px" }}><StatusTag status={s.status} /></td>
                    <td style={{ padding: "10px 14px", textAlign: "right" }} className="tnum">
                      {s.total_amount != null ? fmtMoney(s.total_amount, data.finance.currency) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Recommendations history */}
      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <div>
            <div className="eyebrow"><Sparkles size={12} style={{ verticalAlign: -1, marginRight: 4 }} />Services & upselling</div>
            <h3>Recommendations served</h3>
          </div>
        </div>
        <div className="panel-body">
          {data.recommendations.items.length === 0 ? (
            <div className="panel-empty">No recommendations generated yet.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: "var(--color-muted)" }}>
                  <th style={{ padding: "10px 14px" }}>Service</th>
                  <th style={{ padding: "10px 14px" }}>Category</th>
                  <th style={{ padding: "10px 14px" }}>Reason</th>
                  <th style={{ padding: "10px 14px" }}>Status</th>
                  <th style={{ padding: "10px 14px", textAlign: "right" }}>Score</th>
                </tr>
              </thead>
              <tbody>
                {data.recommendations.items.map((r) => (
                  <tr key={r.id} style={{ borderTop: "1px solid var(--border-hairline)" }}>
                    <td style={{ padding: "10px 14px" }}>{r.service?.name ?? `Service #${r.id}`}</td>
                    <td style={{ padding: "10px 14px", color: "var(--color-muted)", fontSize: 13 }}>{r.service?.category ?? "—"}</td>
                    <td style={{ padding: "10px 14px", fontSize: 13 }}>{r.reasoning ?? "—"}</td>
                    <td style={{ padding: "10px 14px" }}><StatusTag status={r.status} /></td>
                    <td style={{ padding: "10px 14px", textAlign: "right" }} className="tnum">{(r.score * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Face enrollment — attach face data to this guest */}
      <FaceEnrollmentPanel guestId={g.id} guestName={g.full_name} onUpdated={() => {
        // Re-fetch the summary so any newly visible stays/visits refresh too
        fetchGuestSummary(g.id).then((d) => setData(d)).catch(() => {});
      }} />

      {/* Finances roll-up */}
      <div className="panel" style={{ marginTop: 18, marginBottom: 30 }}>
        <div className="panel-head">
          <div>
            <div className="eyebrow"><DollarSign size={12} style={{ verticalAlign: -1, marginRight: 4 }} />Financial</div>
            <h3>Roll-up</h3>
          </div>
        </div>
        <div className="panel-body padded" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          <StatCard label="Lifetime billed" value={fmtMoney(data.finance.total_billed, data.finance.currency)} />
          <StatCard label="Average per stay" value={fmtMoney(data.finance.avg_per_stay, data.finance.currency)} />
          <StatCard label="Services accepted" value={fmtMoney(data.finance.accepted_services_value, data.finance.currency)} />
        </div>
      </div>
    </>
  );
}

// Helper component exported for re-use elsewhere where we want a guest name to
// be a clickable link to the profile page.
export function GuestNameLink({ id, name, vip }: { id: number; name: string; vip?: boolean }) {
  return (
    <Link
      to={`/guests/${id}`}
      style={{ color: "inherit", textDecoration: "none", fontWeight: 500 }}
      onClick={(e) => e.stopPropagation()}
    >
      <span style={{ borderBottom: "1px dashed var(--border-hairline)" }}>{name}</span>
      {vip && <Crown size={12} color="var(--color-gold-600)" style={{ marginLeft: 6, verticalAlign: -1 }} />}
    </Link>
  );
}

/**
 * Attach a face embedding to an EXISTING guest profile. Two sources:
 *   - upload a photo (passport, ID, supplied selfie)
 *   - grab the current lobby camera frame (guest is physically present)
 *
 * Used when a guest profile was created without face data (e.g. from a PMS
 * import) and we want the recognition system to start matching them on
 * arrival. Capacity-aware: max 5 embeddings per guest (FR-1.12).
 */
function FaceEnrollmentPanel({
  guestId,
  guestName,
  onUpdated,
}: {
  guestId: number;
  guestName: string;
  onUpdated: () => void;
}) {
  const { last: liveFeed, connected } = useWebSocketEvent<LiveFeedPayload>("live_feed");
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState<"upload" | "lobby" | null>(null);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [embeddings, setEmbeddings] = useState<GuestEmbedding[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const reloadEmbeddings = () => {
    fetchGuestEmbeddings(guestId).then(setEmbeddings).catch(() => {});
  };

  useEffect(() => { reloadEmbeddings(); }, [guestId]);

  const atCapacity = embeddings.length >= 5;

  function _stripDataUrl(d: string): string {
    const c = d.indexOf(",");
    return c >= 0 ? d.slice(c + 1) : d;
  }

  async function _embedB64(b64: string, source: "upload" | "lobby") {
    setBusy(source);
    setResult(null);
    try {
      const r = await embedFaceForGuest(guestId, b64);
      setResult({ ok: true, msg: `Face added · ${r.embeddings_total}/5 stored` });
      reloadEmbeddings();
      onUpdated();
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "Embedding failed.";
      setResult({ ok: false, msg: detail });
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete(embId: number) {
    if (!window.confirm(
      "Delete this face embedding? Recognition will stop using it immediately.\n\n" +
      "Tip: to refresh a guest's face data, add the new (better) photos FIRST — " +
      "they're checked against the existing ones to confirm it's the same person — " +
      "then delete the old ones."
    )) return;
    setDeletingId(embId);
    setResult(null);
    try {
      await deleteGuestEmbedding(guestId, embId);
      setResult({ ok: true, msg: "Embedding deleted." });
      reloadEmbeddings();
      onUpdated();
    } catch (e: any) {
      setResult({ ok: false, msg: e?.response?.data?.detail ?? "Delete failed." });
    } finally {
      setDeletingId(null);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { alert("Pick an image file."); return; }
    if (file.size > 8 * 1024 * 1024) { alert("Image too large (max 8 MB)."); return; }
    const fr = new FileReader();
    fr.onload = () => _embedB64(_stripDataUrl(String(fr.result || "")), "upload");
    fr.readAsDataURL(file);
    e.target.value = "";
  }

  async function captureFromLobby() {
    if (!liveFeed?.frame_b64) {
      alert(connected ? "No camera frame yet — wait for the Pi to push one." : "Lobby feed offline.");
      return;
    }
    await _embedB64(liveFeed.frame_b64, "lobby");
  }

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <div className="panel-head">
        <div>
          <div className="eyebrow"><Camera size={12} style={{ verticalAlign: -1, marginRight: 4 }} />Face data</div>
          <h3>Attach face to this profile</h3>
        </div>
        <div className="right t-caption" style={{ color: "var(--color-muted)" }}>
          {embeddings.length}/5 embeddings · FR-1.12
        </div>
      </div>
      <div className="panel-body padded">
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 14 }}>
          Add a face embedding so the recognition system can match <strong>{guestName}</strong>{" "}
          on arrival. Use a passport/ID scan, or grab the current lobby feed if they're at the desk now.
          New faces are <strong>checked against the existing ones</strong> — if it isn't the same
          person, the add is rejected so two people can't be merged into one profile.
        </p>

        {/* Existing embeddings — delete to refresh a guest's face data */}
        {embeddings.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="t-label" style={{ marginBottom: 8 }}>
              Stored face embeddings
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {embeddings.map((e, i) => (
                <div
                  key={e.id}
                  className="row"
                  style={{
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px 12px",
                    border: "1px solid var(--border-hairline)",
                    borderRadius: 4,
                    background: "var(--bg-canvas)",
                  }}
                >
                  <div className="row" style={{ gap: 10, alignItems: "center", minWidth: 0 }}>
                    <ScanFace size={16} style={{ color: "var(--color-muted)", flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>
                        Face #{i + 1}
                        <span style={{ color: "var(--color-muted)", fontWeight: 400 }}>
                          {" · "}{e.source}
                        </span>
                      </div>
                      <div className="t-caption tnum" style={{ color: "var(--color-muted)" }}>
                        {e.quality_score != null ? `q=${e.quality_score.toFixed(2)} · ` : ""}
                        {fmtDateTime(e.created_at)}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={deletingId === e.id}
                    onClick={() => handleDelete(e.id)}
                    title="Delete this embedding"
                    style={{ color: "#7a2a2a", flexShrink: 0 }}
                  >
                    <Trash2 size={13} /> {deletingId === e.id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {atCapacity && (
          <div
            style={{
              marginBottom: 14, padding: 10, borderRadius: 4, fontSize: 13,
              background: "var(--color-assistance-bg)",
              border: "1px solid var(--color-assistance-tint)",
            }}
          >
            At the 5-embedding limit. Delete one above before adding a fresher photo.
          </div>
        )}

        <div className="grid-2col" style={{ gap: 12 }}>
          {/* Upload card */}
          <div
            onClick={() => !busy && !atCapacity && fileRef.current?.click()}
            style={{
              padding: 18,
              border: "1.5px dashed var(--border-hairline)",
              borderRadius: 6,
              background: "rgba(0,30,60,0.02)",
              cursor: atCapacity ? "not-allowed" : busy ? "wait" : "pointer",
              opacity: atCapacity ? 0.5 : 1,
              textAlign: "center",
            }}
          >
            <FileImage size={22} color="var(--color-muted)" />
            <div style={{ fontSize: 14, fontWeight: 500, marginTop: 8 }}>Upload photo</div>
            <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4 }}>
              Passport, ID, or supplied selfie · JPEG / PNG
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: "none" }}
              onChange={onFile}
              disabled={atCapacity}
            />
            <div style={{ marginTop: 10 }}>
              <span className="btn btn-primary btn-sm" style={atCapacity ? { pointerEvents: "none", opacity: 0.6 } : undefined}>
                <Upload size={12} /> {busy === "upload" ? "Embedding…" : "Choose file"}
              </span>
            </div>
          </div>

          {/* Lobby feed card */}
          <div
            style={{
              padding: 18,
              border: "1.5px dashed var(--border-hairline)",
              borderRadius: 6,
              background: "rgba(0,30,60,0.02)",
              textAlign: "center",
            }}
          >
            <Camera size={22} color="var(--color-muted)" />
            <div style={{ fontSize: 14, fontWeight: 500, marginTop: 8 }}>Capture from lobby</div>
            <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4 }}>
              {connected
                ? liveFeed
                  ? "Guest is in front of the camera right now"
                  : "Waiting for first frame…"
                : "Lobby feed offline"}
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={!liveFeed || !!busy || atCapacity}
              onClick={captureFromLobby}
              style={{ marginTop: 10 }}
            >
              <Camera size={12} /> {busy === "lobby" ? "Embedding…" : "Capture frame"}
            </button>
          </div>
        </div>

        {result && (
          <div
            style={{
              marginTop: 14,
              padding: 10,
              borderRadius: 4,
              background: result.ok ? "rgba(48,128,72,0.08)" : "rgba(199,46,46,0.08)",
              color: result.ok ? "#286143" : "#7a2a2a",
              fontSize: 13,
            }}
          >
            {result.ok ? "✓" : "✗"} {result.msg}
          </div>
        )}
      </div>
    </div>
  );
}
