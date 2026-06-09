import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Star, StarOff } from "lucide-react";
import {
  fetchWatchlist,
  searchGuests,
  setGuestWatchlist,
  Guest,
} from "../services/api";

export default function WatchlistPage() {
  const [list, setList] = useState<Guest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Guest[]>([]);
  const [searching, setSearching] = useState(false);

  const [reasonDrafts, setReasonDrafts] = useState<Record<number, string>>({});

  const refresh = async () => {
    setLoading(true);
    try {
      const rows = await fetchWatchlist();
      setList(rows);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  async function runSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) { setResults([]); return; }
    setSearching(true);
    try {
      const rows = await searchGuests(q);
      setResults(rows);
    } finally {
      setSearching(false);
    }
  }

  async function toggle(g: Guest, on: boolean) {
    setBusy(g.id);
    try {
      const reason = reasonDrafts[g.id] ?? g.watch_reason ?? "";
      await setGuestWatchlist(g.id, on, on ? reason : undefined);
      await refresh();
      // Also reflect the change in the local results list so the star flips
      setResults((prev) => prev.map((r) => (r.id === g.id ? { ...r, is_watched: on } : r)));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Security</div>
        <h1 className="page-h1">Watchlist</h1>
        <p className="page-lead">
          Flag enrolled guests for a real-time alert whenever the lobby camera recognises them.
          A high-severity <em>WANTED</em> alert is fired the moment they're identified.
        </p>
      </header>

      <div className="grid-2col">
        {/* Current watchlist */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Active</div>
              <h3>Watched guests · {list.length}</h3>
            </div>
          </div>
          <div className="panel-body">
            {loading ? (
              <div className="panel-empty">Loading…</div>
            ) : list.length === 0 ? (
              <div className="panel-empty">No guests on the watchlist yet. Use the search panel to add one.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  {list.map((g) => (
                    <tr key={g.id} style={{ borderTop: "1px solid var(--border-hairline)" }}>
                      <td style={{ padding: "12px 14px" }}>
                        <Link to={`/guests/${g.id}`} style={{ color: "inherit", textDecoration: "none", fontWeight: 500 }}>
                          <span style={{ borderBottom: "1px dashed var(--border-hairline)" }}>{g.full_name}</span>
                        </Link>
                        {g.watch_reason && (
                          <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4 }}>
                            {g.watch_reason}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={busy === g.id}
                          onClick={() => toggle(g, false)}
                          title="Remove from watchlist"
                        >
                          <StarOff size={14} /> Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Add to watchlist */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Add</div>
              <h3>Find a guest</h3>
            </div>
          </div>
          <div className="panel-body padded">
            <form onSubmit={runSearch} className="row" style={{ gap: 8, marginBottom: 14 }}>
              <input
                type="text"
                placeholder="Search by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1, padding: "8px 10px", border: "1px solid var(--border-hairline)" }}
              />
              <button type="submit" className="btn btn-primary" disabled={searching}>
                <Search size={14} /> {searching ? "…" : "Search"}
              </button>
            </form>

            {results.length === 0 ? (
              <div className="panel-empty">Type a name and hit search to find an enrolled guest.</div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {results.map((g) => (
                  <div
                    key={g.id}
                    style={{
                      padding: 12,
                      border: "1px solid var(--border-hairline)",
                      borderRadius: 4,
                    }}
                  >
                    <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                      <div>
                        <Link to={`/guests/${g.id}`} style={{ color: "inherit", textDecoration: "none", fontWeight: 500 }}>
                          <span style={{ borderBottom: "1px dashed var(--border-hairline)" }}>{g.full_name}</span>
                        </Link>
                        <div style={{ fontSize: 12, color: "var(--color-muted)" }}>
                          {g.email ?? "—"} · {g.status}
                        </div>
                      </div>
                      {g.is_watched ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          disabled={busy === g.id}
                          onClick={() => toggle(g, false)}
                        >
                          <StarOff size={14} /> Unwatch
                        </button>
                      ) : (
                        <button
                          className="btn btn-gold btn-sm"
                          disabled={busy === g.id}
                          onClick={() => toggle(g, true)}
                        >
                          <Star size={14} /> Watch
                        </button>
                      )}
                    </div>
                    {!g.is_watched && (
                      <input
                        type="text"
                        placeholder="Optional reason (shown in the alert)"
                        value={reasonDrafts[g.id] ?? ""}
                        onChange={(e) => setReasonDrafts((d) => ({ ...d, [g.id]: e.target.value }))}
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          fontSize: 13,
                          border: "1px solid var(--border-hairline)",
                        }}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
