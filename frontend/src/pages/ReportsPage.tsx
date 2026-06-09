import { useEffect, useState } from "react";
import { BedDouble, Bell, Download, Users, Plane } from "lucide-react";
import { api, fetchSystemStatus, getToken, SystemStatus } from "../services/api";

interface Stats {
  date: string;
  guests_total: number;
  guests_identified_today: number;
  alerts_today: number;
  alerts_open: number;
  alerts_by_severity: Record<string, number>;
  recommendations_today: number;
  recommendations_accepted_today: number;
  embeddings_total: number;
}

export default function ReportsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Stats>("/api/system/stats")
      .then((r) => setStats(r.data))
      .catch((e) => setError(e?.response?.data?.detail ?? "Failed to load stats"));
    fetchSystemStatus().then(setStatus).catch(() => {});
  }, []);

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Insights</div>
        <h1 className="page-h1">Reports</h1>
        <p className="page-lead">
          A snapshot of today's reception activity, system health, and the alert
          breakdown by severity.
        </p>
      </header>

      {error ? (
        <div className="panel-empty" style={{ color: "var(--color-security-fg)" }}>{error}</div>
      ) : !stats ? (
        <div className="panel-empty">Loading…</div>
      ) : (
        <>
          <p className="t-caption" style={{ marginBottom: 12 }}>For {stats.date} (UTC)</p>

          <div className="grid-stat" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
            <StatTile label="Guests in DB" value={stats.guests_total} />
            <StatTile label="Identified today" value={stats.guests_identified_today} delta="arrivals" deltaTone="up" />
            <StatTile label="Alerts today" value={stats.alerts_today} />
            <StatTile label="Open alerts" value={stats.alerts_open} delta="pending" deltaTone="down" />
            <StatTile label="Recs generated" value={stats.recommendations_today} />
            <StatTile label="Recs accepted" value={stats.recommendations_accepted_today} delta="conversions" deltaTone="up" />
            <StatTile label="Embeddings" value={stats.embeddings_total} />
            {status && <StatTile label="Uptime (s)" value={status.server_uptime_seconds} />}
          </div>

          {/* FR-6.12 — CSV export buttons */}
          <div className="panel" style={{ marginTop: 18 }}>
            <div className="panel-head">
              <div>
                <div className="eyebrow"><Download size={12} style={{ verticalAlign: -1, marginRight: 4 }} />Export</div>
                <h3>Download CSV reports</h3>
              </div>
            </div>
            <div className="panel-body padded">
              <p className="t-caption" style={{ color: "var(--color-muted)", marginBottom: 14 }}>
                Bearer-token auth is applied automatically so the file downloads in the same browser session.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                <CsvExportButton path="/api/exports/guests"       icon={Users}      label="Guests" />
                <CsvExportButton path="/api/exports/visits"       icon={Plane}      label="Visits" />
                <CsvExportButton path="/api/exports/reservations" icon={BedDouble}  label="Reservations" />
                <CsvExportButton path="/api/exports/alerts"       icon={Bell}       label="Alerts" />
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <div className="eyebrow">Today</div>
                <h3>Alerts by severity</h3>
              </div>
            </div>
            {Object.keys(stats.alerts_by_severity).length === 0 ? (
              <div className="empty">
                <div className="h">No alerts today</div>
                <div className="s">Quiet shift so far.</div>
              </div>
            ) : (
              <div className="panel-body padded">
                {Object.entries(stats.alerts_by_severity)
                  .sort((a, b) => Number(b[0]) - Number(a[0]))
                  .map(([sev, n]) => {
                    const max = Math.max(...Object.values(stats.alerts_by_severity));
                    const pct = max > 0 ? (n / max) * 100 : 0;
                    const colour = Number(sev) >= 3 ? "var(--color-security-fg)" : Number(sev) === 2 ? "var(--color-assistance-fg)" : "var(--color-vip-fg)";
                    return (
                      <div key={sev} style={{ marginBottom: 10 }}>
                        <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                          <span className="t-label">Severity {sev}</span>
                          <span className="tnum t-body-sm" style={{ fontWeight: 600 }}>{n}</span>
                        </div>
                        <div style={{ height: 6, background: "var(--color-ink-100)", borderRadius: 999, overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: colour }} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}

function StatTile({ label, value, delta, deltaTone }: { label: string; value: number; delta?: string; deltaTone?: "up" | "down" }) {
  return (
    <div className="stat">
      <div className="lbl">{label}</div>
      <div className="val">{value}</div>
      {delta && <div className={`delta${deltaTone ? " " + deltaTone : ""}`}>{delta}</div>}
    </div>
  );
}

function CsvExportButton({ path, icon: Icon, label }: { path: string; icon: any; label: string }) {
  const [busy, setBusy] = useState(false);

  async function download() {
    setBusy(true);
    try {
      // Use the api axios instance so the JWT bearer header is applied; we
      // get the bytes and trigger a synthetic <a download> click for the
      // browser save dialog. Without this, hitting /api/exports/* via a raw
      // <a href> would 401 (no Authorization header on plain GETs).
      const r = await api.get(path, { responseType: "blob" });
      const blob = new Blob([r.data], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const fileName = path.split("/").pop() + `_${new Date().toISOString().slice(0, 10)}.csv`;
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e?.response?.data?.detail ?? `Export failed for ${path}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className="btn btn-primary"
      onClick={download}
      disabled={busy || !getToken()}
      style={{ justifyContent: "center", padding: 10 }}
    >
      <Icon size={14} /> {busy ? "Exporting…" : label}
    </button>
  );
}
