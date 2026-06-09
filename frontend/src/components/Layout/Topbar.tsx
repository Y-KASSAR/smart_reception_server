import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { wsClient } from "../../services/websocket";

const PAGE_TITLES: Record<string, { eyebrow: string; title: string }> = {
  "/":          { eyebrow: "Real-time", title: "Live Monitor" },
  "/alerts":    { eyebrow: "Operations", title: "Alerts" },
  "/guests":    { eyebrow: "Records",    title: "Guest Lookup" },
  "/enrollment":{ eyebrow: "Records",    title: "New Enrollment" },
  "/reports":   { eyebrow: "Insights",   title: "Reports" },
  "/settings":  { eyebrow: "System",     title: "Settings" },
};

export default function Topbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [wsConnected, setWsConnected] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => wsClient.onStatus(setWsConnected), []);

  const meta = PAGE_TITLES[location.pathname] ?? { eyebrow: "View", title: "Dashboard" };

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (term.length >= 2) {
      navigate(`/guests?q=${encodeURIComponent(term)}`);
    }
  }

  return (
    <header className="topbar">
      <div>
        <div className="tb-eyebrow">{meta.eyebrow}</div>
        <div className="tb-title">{meta.title}</div>
      </div>

      <form className="tb-search" onSubmit={onSubmit}>
        <Search />
        <input
          type="search"
          placeholder="Search guests, alerts…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </form>

      <div className={`tb-live${wsConnected ? "" : " off"}`}>
        <span className="live-dot" />
        {wsConnected ? "Live" : "Offline"}
      </div>
    </header>
  );
}
