import { useEffect, useMemo, useState } from "react";
import {
  Check,
  CheckCheck,
  ShieldAlert,
  HelpCircle,
  Crown,
  Clock,
  Ban,
  CheckCircle2,
} from "lucide-react";
import {
  acknowledgeAlert,
  Alert,
  fetchAlerts,
  resolveAlert,
} from "../services/api";
import { useWebSocketEvent } from "../hooks/useWebSocket";

const STATUS_OPTIONS = ["all", "pending", "acknowledged", "resolved"] as const;
type Status = (typeof STATUS_OPTIONS)[number];

const ALERT_ICON: Record<string, { cls: string; Icon: any }> = {
  security:    { cls: "security",    Icon: ShieldAlert },
  assistance:  { cls: "assistance",  Icon: HelpCircle },
  vip_arrival: { cls: "vip",         Icon: Crown },
  arrival:     { cls: "vip",         Icon: Crown },
  due_out:     { cls: "dueout",      Icon: Clock },
  wanted:      { cls: "wanted",      Icon: Ban },
  resolved:    { cls: "resolved",    Icon: CheckCircle2 },
};
function iconFor(type: string, status: string) {
  if (status === "resolved") return { cls: "resolved", Icon: CheckCircle2 };
  return ALERT_ICON[type] ?? { cls: "assistance", Icon: HelpCircle };
}

function relativeTime(iso: string): string {
  const d = new Date(iso).getTime();
  const dt = Date.now() - d;
  const m = Math.floor(dt / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleString();
}

export default function AlertsPage() {
  const [status, setStatus] = useState<Status>("pending");
  const [minSeverity, setMinSeverity] = useState<number>(0);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const { last: push } = useWebSocketEvent<any>("alert_push");

  const reload = () => {
    setLoading(true);
    fetchAlerts(status === "all" ? undefined : status)
      .then(setAlerts)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [status]);
  useEffect(() => { if (push) reload(); }, [push?.alert_id]);

  const filtered = useMemo(
    () =>
      alerts
        // Guard: only show rows matching the selected status, even if the
        // backend ever returns extra (keeps the list in sync with the badge).
        .filter((a) => status === "all" || a.status === status)
        .filter((a) => a.severity >= minSeverity)
        .sort((a, b) => b.severity - a.severity || b.id - a.id),
    [alerts, minSeverity, status]
  );

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Operations</div>
        <h1 className="page-h1">Alerts</h1>
        <p className="page-lead">
          Every event triggered by the lobby monitor, alert notifier, and edge pipeline.
          Acknowledge once seen, resolve when the situation is closed.
        </p>
      </header>

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-head">
          <div className="row" style={{ gap: 14 }}>
            <div>
              <div className="t-label" style={{ marginBottom: 4 }}>Status</div>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as Status)}
                style={{
                  padding: "5px 10px",
                  border: "1px solid var(--border-hairline)",
                  borderRadius: 4,
                  fontFamily: "inherit",
                  fontSize: 13,
                  background: "var(--bg-canvas)",
                }}
              >
                {STATUS_OPTIONS.map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </div>
            <div>
              <div className="t-label" style={{ marginBottom: 4 }}>Min severity</div>
              <select
                value={minSeverity}
                onChange={(e) => setMinSeverity(Number(e.target.value))}
                style={{
                  padding: "5px 10px",
                  border: "1px solid var(--border-hairline)",
                  borderRadius: 4,
                  fontFamily: "inherit",
                  fontSize: 13,
                  background: "var(--bg-canvas)",
                }}
              >
                <option value={0}>any</option>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3 (high)</option>
              </select>
            </div>
          </div>
          <div className="right">
            <button className="btn btn-secondary btn-sm" onClick={reload}>Refresh</button>
          </div>
        </div>

        {loading && alerts.length === 0 ? (
          <div className="panel-empty">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="empty">
            <CheckCircle2 className="ic" />
            <div className="h">No alerts match the current filters</div>
            <div className="s">Try widening the status or severity.</div>
          </div>
        ) : (
          <div className="panel-body">
            {filtered.map((a) => {
              const { cls, Icon } = iconFor(a.alert_type, a.status);
              return (
                <div key={a.id} className={`alert-row ${a.status}`}>
                  <div className={`alert-icon ${cls}`}>
                    <Icon />
                  </div>
                  <div className="alert-body">
                    <div className="eyebrow">
                      {a.severity >= 3 && a.status === "pending" && <span className="pdot" />}
                      {a.alert_type.replace(/_/g, " ")}
                      <span className="sep">·</span>sev {a.severity}
                      <span className="sep">·</span>
                      <span style={{ textTransform: "uppercase" }}>{a.status}</span>
                    </div>
                    <div className="title">{a.title}</div>
                    {a.description && (
                      <div className="meta" style={{ marginTop: 4 }}>{a.description}</div>
                    )}
                    <div className="meta">
                      {relativeTime(a.created_at)}
                      {a.location && (<><span className="sep">·</span>{a.location}</>)}
                      {a.guest_id && (<><span className="sep">·</span>guest #{a.guest_id}</>)}
                      {a.acknowledged_by && (<><span className="sep">·</span>by {a.acknowledged_by}</>)}
                    </div>
                  </div>
                  <div className="alert-actions">
                    {a.status === "pending" && (
                      <button className="btn btn-ghost btn-sm" onClick={() => acknowledgeAlert(a.id, 1).then(reload)}>
                        <Check /> Ack
                      </button>
                    )}
                    {a.status !== "resolved" && (
                      <button className="btn btn-secondary btn-sm" onClick={() => resolveAlert(a.id).then(reload)}>
                        <CheckCheck /> Resolve
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
