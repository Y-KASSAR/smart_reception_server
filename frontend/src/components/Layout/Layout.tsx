import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { ToastProvider } from "../Toast/Toast";

/**
 * App shell — fixed sidebar on the left, sticky topbar over the page area.
 * Layout grid set in global.css `.app`. Wrapped in ToastProvider so the
 * `toast.success/error/info(...)` module-level API works from any page.
 */
export default function Layout() {
  return (
    <ToastProvider>
      <div className="app">
        <Sidebar />
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <Topbar />
          <div className="page">
            <Outlet />
          </div>
        </div>
      </div>
    </ToastProvider>
  );
}
