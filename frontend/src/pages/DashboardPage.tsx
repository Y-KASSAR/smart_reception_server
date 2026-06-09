import LiveFeedPanel from "../components/LiveFeed/LiveFeedPanel";
import GuestInfoPanel from "../components/GuestInfo/GuestInfoPanel";
import RecommendationPanel from "../components/Recommendations/RecommendationPanel";
import AlertPanel from "../components/Alerts/AlertPanel";
import LobbyOverview from "../components/Monitoring/LobbyOverview";
import LobbyMap from "../components/Monitoring/LobbyMap";

export default function DashboardPage() {
  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Real-time</div>
        <h1 className="page-h1">Lobby at a glance</h1>
        <p className="page-lead">
          Live camera feed, current occupancy, and any guests recognised in the past
          few seconds. Alerts and upsell suggestions update the moment the model fires.
        </p>
      </header>

      <LobbyOverview />

      <div className="grid-2col" style={{ marginBottom: 20 }}>
        <LiveFeedPanel />
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <GuestInfoPanel />
          <RecommendationPanel />
        </div>
      </div>

      <LobbyMap />

      <AlertPanel />
    </>
  );
}
