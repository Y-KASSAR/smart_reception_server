import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BedDouble,
  Bell,
  Eye,
  Languages,
  LogOut,
  Settings,
  UserPlus,
  Users,
} from "lucide-react";
import {
  clearAuth,
  currentRole,
  currentUsername,
  fetchPendingAlerts,
} from "../../services/api";
import { wsClient } from "../../services/websocket";
import { useWebSocketEvent } from "../../hooks/useWebSocket";

const NAV_PRIMARY = [
  { to: "/", label: "Live Monitor", icon: Activity, end: true },
  { to: "/alerts", label: "Alerts", icon: Bell, badge: "alerts" as const },
  { to: "/guests", label: "Guest Lookup", icon: Users },
  { to: "/watchlist", label: "Watchlist", icon: Eye },
  { to: "/translation", label: "Live Translation", icon: Languages },
];

const NAV_SECONDARY = [
  { to: "/reservations", label: "Reservations", icon: BedDouble },
  { to: "/enrollment", label: "Enrollment", icon: UserPlus },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

export default function Sidebar() {
  const navigate = useNavigate();
  const [pendingAlertCount, setPendingAlertCount] = useState<number>(0);

  // Refresh badge count whenever a new alert is pushed
  const { last: push } = useWebSocketEvent<any>("alert_push");

  useEffect(() => {
    let cancelled = false;
    fetchPendingAlerts()
      .then((al) => {
        if (!cancelled) setPendingAlertCount(al.length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [push?.alert_id]);

  const handleLogout = () => {
    clearAuth();
    wsClient.stop();
    navigate("/login", { replace: true });
  };

  const username = currentUsername() ?? "Staff";
  const role = currentRole() ?? "—";

  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <div className="logo">S</div>
        <div>
          <div className="s">Smart Reception</div>
          <div className="n">Assistant</div>
        </div>
      </div>

      <div className="sb-section-label">Monitoring</div>
      {NAV_PRIMARY.map(({ to, label, icon: Icon, end, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => `sb-item${isActive ? " active" : ""}`}
        >
          <Icon />
          <span>{label}</span>
          {badge === "alerts" && pendingAlertCount > 0 && (
            <span className="sb-count danger">{pendingAlertCount}</span>
          )}
        </NavLink>
      ))}

      <div className="sb-section-label">Management</div>
      {NAV_SECONDARY.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => `sb-item${isActive ? " active" : ""}`}
        >
          <Icon />
          <span>{label}</span>
        </NavLink>
      ))}

      <div className="sb-staff">
        <div className="av">{initials(username)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="nm" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {username}
          </div>
          <div className="rl" style={{ textTransform: "capitalize" }}>{role}</div>
        </div>
        <button className="logout" onClick={handleLogout} title="Sign out">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
