import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { useWebSocketEvent } from "../../hooks/useWebSocket";

interface MonitoringStatus {
  total_persons: number;
  in_house_count: number;
  unknown_count: number;
  flagged_count: number;
  tracks: {
    track_id: number;
    is_known: boolean;
    guest_id: number | null;
    dwell_seconds: number;
    alerts_fired: string[];
  }[];
}

export default function LobbyOverview() {
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const { last } = useWebSocketEvent<any>("detection_update");

  useEffect(() => {
    let cancelled = false;
    api.get<MonitoringStatus>("/api/monitoring/status")
      .then((r) => !cancelled && setStatus(r.data))
      .catch(() => {});
    return () => { cancelled = true; };
  }, [last]);

  useEffect(() => {
    const id = setInterval(() => {
      api.get<MonitoringStatus>("/api/monitoring/status").then((r) => setStatus(r.data)).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, []);

  const s = status ?? { total_persons: 0, in_house_count: 0, unknown_count: 0, flagged_count: 0, tracks: [] };

  return (
    <div className="grid-stat">
      <Stat label="Persons" value={s.total_persons} />
      <Stat label="In-house" value={s.in_house_count} delta="recognised" deltaTone="up" />
      <Stat label="Unknown" value={s.unknown_count} delta="unrecognised" />
      <Stat label="Flagged" value={s.flagged_count} delta="alert fired" deltaTone="down" />
    </div>
  );
}

function Stat({
  label,
  value,
  delta,
  deltaTone,
}: {
  label: string;
  value: number;
  delta?: string;
  deltaTone?: "up" | "down";
}) {
  return (
    <div className="stat">
      <div className="lbl">{label}</div>
      <div className="val">{value}</div>
      {delta && <div className={`delta${deltaTone ? " " + deltaTone : ""}`}>{delta}</div>}
    </div>
  );
}
