import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Crown, Eye, EyeOff } from "lucide-react";
import { api, Guest, setGuestWatchlist } from "../services/api";

function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

export default function GuestLookupPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [results, setResults] = useState<Guest[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Guest | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      setLoading(true);
      api
        .get<Guest[]>(`/api/guests/search?q=${encodeURIComponent(q.trim())}`)
        .then((r) => setResults(r.data))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
      setParams(q.trim() ? { q: q.trim() } : {});
    }, 300);
    return () => clearTimeout(t);
  }, [q, setParams]);

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Records</div>
        <h1 className="page-h1">Guest lookup</h1>
        <p className="page-lead">
          Search by name, email, phone, or ID/passport number. Open a row to
          see their profile, preferences, and visit history at a glance.
        </p>
      </header>

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-body padded">
          <input
            type="search"
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Type a name, email, phone, or ID number (min 2 chars)…"
            style={{
              width: "100%",
              padding: "10px 14px",
              border: "1px solid var(--border-hairline)",
              borderRadius: 4,
              fontFamily: "inherit",
              fontSize: 14,
              background: "var(--bg-canvas)",
            }}
          />
        </div>
      </div>

      <div className="grid-2col">
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Matches</div>
              <h3>Results {loading && <span className="t-caption">· searching…</span>}</h3>
            </div>
            <div className="right t-caption tnum">{results.length}</div>
          </div>
          {results.length === 0 ? (
            <div className="empty">
              <div className="h">{q.length < 2 ? "Awaiting input" : "No matches"}</div>
              <div className="s">{q.length < 2 ? "Type at least 2 characters." : "Try a different spelling."}</div>
            </div>
          ) : (
            <table className="gtable">
              <thead>
                <tr>
                  <th>Guest</th>
                  <th>Email</th>
                  <th>Nat.</th>
                </tr>
              </thead>
              <tbody>
                {results.map((g) => (
                  <tr key={g.id} onClick={() => setSelected(g)}>
                    <td>
                      <div className="gname">
                        <div className={`av sm${g.vip_status ? " vip" : ""}`}>{initials(g.full_name)}</div>
                        <div>
                          <strong>{g.full_name}</strong>
                          {g.vip_status && <span className="sub" style={{ color: "var(--color-gold-700)" }}>VIP</span>}
                        </div>
                      </div>
                    </td>
                    <td>{g.email ?? "—"}</td>
                    <td>{g.nationality ? <span className="nat">{g.nationality}</span> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Detail</div>
              <h3>Profile</h3>
            </div>
            {selected?.vip_status && <Crown size={16} color="var(--color-gold-600)" />}
          </div>
          {!selected ? (
            <div className="empty">
              <div className="h">No guest selected</div>
              <div className="s">Click a row to see their full profile.</div>
            </div>
          ) : (
            <div className="panel-body padded">
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                <div className="t-h3">{selected.full_name}</div>
                <WatchToggle
                  guest={selected}
                  onChange={(updated) => {
                    setSelected(updated);
                    setResults((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
                  }}
                />
              </div>
              <div className="row" style={{ gap: 6, marginBottom: 14 }}>
                {selected.vip_status && (<span className="chip vip"><span className="d" />VIP</span>)}
                <span className="chip neutral"><span className="d" />{selected.status}</span>
                {selected.is_watched && (
                  <span className="chip" style={{ color: "#001E3C", background: "rgba(0,30,60,0.08)" }}>
                    <span className="d" />Watched
                  </span>
                )}
              </div>

              <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", rowGap: 8, columnGap: 12, fontSize: 13 }}>
                <Row k="Email" v={selected.email ?? "—"} />
                <Row k="Phone" v={selected.phone ?? "—"} mono />
                <Row k="Nationality" v={selected.nationality ?? "—"} />
                {selected.preferences && <Row k="Preferences" v={selected.preferences} mono />}
                {selected.is_watched && selected.watch_reason && (
                  <Row k="Watch reason" v={selected.watch_reason} />
                )}
              </dl>

              {selected.notes && (
                <p className="t-editorial" style={{ marginTop: 14, borderLeft: "2px solid var(--color-gold-300)", paddingLeft: 10 }}>
                  {selected.notes}
                </p>
              )}

              <Link
                to={`/guests/${selected.id}`}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center", marginTop: 16 }}
              >
                Open full profile <ArrowRight size={14} />
              </Link>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Row({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <>
      <dt className="t-label">{k}</dt>
      <dd className={mono ? "t-mono" : ""} style={{ margin: 0 }}>{v}</dd>
    </>
  );
}

function WatchToggle({ guest, onChange }: { guest: Guest; onChange: (g: Guest) => void }) {
  const [busy, setBusy] = useState(false);
  const watched = !!guest.is_watched;

  async function toggle() {
    if (busy) return;
    if (!watched) {
      const reason = window.prompt(
        `Add ${guest.full_name} to the watchlist. Reason shown to staff in the alert (optional):`,
        ""
      );
      if (reason === null) return; // cancelled
      setBusy(true);
      try {
        const updated = await setGuestWatchlist(guest.id, true, reason || undefined);
        onChange(updated);
      } finally {
        setBusy(false);
      }
    } else {
      setBusy(true);
      try {
        const updated = await setGuestWatchlist(guest.id, false);
        onChange(updated);
      } finally {
        setBusy(false);
      }
    }
  }

  return (
    <button
      type="button"
      className={`btn ${watched ? "btn-ghost" : "btn-gold"} btn-sm`}
      onClick={toggle}
      disabled={busy}
      title={watched ? "Remove from watchlist" : "Add to watchlist"}
    >
      {watched ? <EyeOff size={14} /> : <Eye size={14} />}
      {watched ? "Unwatch" : "Watch"}
    </button>
  );
}
