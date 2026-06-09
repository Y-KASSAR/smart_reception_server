import { useEffect, useMemo, useState } from "react";
import { Check, CheckCheck, ShieldAlert, HelpCircle, Crown, Clock, Ban, CheckCircle2 } from "lucide-react";
import { useWebSocketEvent } from "../../hooks/useWebSocket";
import {
  acknowledgeAlert,
  Alert,
  fetchPendingAlerts,
  resolveAlert,
} from "../../services/api";

interface AlertPushPayload {
  event: "alert_push";
  alert_id?: number;
  alert_type?: string;
  title?: string;
  severity?: number;
}

const ALERT_ICON: Record<string, { cls: string; Icon: any }> = {
  security:    { cls: "security",    Icon: ShieldAlert },
  assistance:  { cls: "assistance",  Icon: HelpCircle },
  vip_arrival: { cls: "vip",         Icon: Crown },
  arrival:     { cls: "vip",         Icon: Crown },
  due_out:     { cls: "dueout",      Icon: Clock },
  wanted:      { cls: "wanted",      Icon: Ban },
};

function iconFor(type: string) {
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

export default function AlertPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const { last: push } = useWebSocketEvent<AlertPushPayload>("alert_push");

  const reload = () => {
    setLoading(true);
    fetchPendingAlerts()
      .then(setAlerts)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);
  useEffect(() => { if (push) reload(); }, [push?.alert_id]);

  const sorted = useMemo(
    () => [...alerts].sort((a, b) => b.severity - a.severity || (b.id - a.id)),
    [alerts]
  );

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <div className="eyebrow">Live</div>
          <h3>Pending alerts <span className="t-caption tnum">· {sorted.length}</span></h3>
        </div>
        <div className="right">
          <button className="btn btn-ghost btn-sm" onClick={reload}>Refresh</button>
        </div>
      </div>

      {loading && alerts.length === 0 ? (
        <div className="panel-empty">Loading…</div>
      ) : sorted.length === 0 ? (
        <div className="empty">
          <CheckCircle2 className="ic" />
          <div className="h">All clear</div>
          <div className="s">No pending alerts at the moment.</div>
        </div>
      ) : (
        <div className="panel-body">
          {sorted.map((a) => {
            const { cls, Icon } = iconFor(a.alert_type);
            return (
              <div key={a.id} className={`alert-row ${a.status}`}>
                <div className={`alert-icon ${cls}`}>
                  <Icon />
                </div>
                <div className="alert-body">
                  <div className="eyebrow">
                    {a.severity >= 3 && <span className="pdot" />}
                    {a.alert_type.replace(/_/g, " ")}
                    <span className="sep">·</span>
                    sev {a.severity}
                  </div>
                  <div className="title">{a.title}</div>
                  <div className="meta">
                    {relativeTime(a.created_at)}
                    {a.location && (<><span className="sep">·</span>{a.location}</>)}
                    {a.guest_id && (<><span className="sep">·</span>guest #{a.guest_id}</>)}
                  </div>
                </div>
                <div className="alert-actions">
                  <button className="btn btn-ghost btn-sm" title="Acknowledge" onClick={() => acknowledgeAlert(a.id, 1).then(reload)}>
                    <Check />
                  </button>
                  <button className="btn btn-secondary btn-sm" title="Resolve" onClick={() => resolveAlert(a.id).then(reload)}>
                    <CheckCheck />
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
