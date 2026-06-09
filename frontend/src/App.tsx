import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { isAuthenticated } from "./services/api";
import { wsClient } from "./services/websocket";
import Layout from "./components/Layout/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import AlertsPage from "./pages/AlertsPage";
import GuestLookupPage from "./pages/GuestLookupPage";
import EnrollmentPage from "./pages/EnrollmentPage";
import GuestProfilePage from "./pages/GuestProfilePage";
import LiveTranslationPage from "./pages/LiveTranslationPage";
import ReportsPage from "./pages/ReportsPage";
import ReservationsPage from "./pages/ReservationsPage";
import SettingsPage from "./pages/SettingsPage";
import WatchlistPage from "./pages/WatchlistPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

export default function App() {
  useEffect(() => {
    if (isAuthenticated()) wsClient.start();
    return () => wsClient.stop();
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="guests" element={<GuestLookupPage />} />
        <Route path="guests/:id" element={<GuestProfilePage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="reservations" element={<ReservationsPage />} />
        <Route path="translation" element={<LiveTranslationPage />} />
        <Route path="enrollment" element={<EnrollmentPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
