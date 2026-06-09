/**
 * NFR-4.3 — Friendly error / success notifications
 *
 * Replaces the ad-hoc `alert(...)` calls scattered across pages with a
 * single non-blocking toast surface anchored to the bottom-right of the
 * viewport. Toasts auto-dismiss after a tone-specific duration (longer for
 * errors so the operator has time to read).
 *
 * Public API (imported from anywhere in the SPA):
 *
 *     import { toast } from "../components/Toast/Toast";
 *     toast.success("Guest enrolled");
 *     toast.error("Photo did not contain a clear face");
 *     toast.info("Pipeline engaged");
 *
 * The provider must be mounted ONCE near the app root (Layout.tsx).
 */
import { createContext, ReactNode, useCallback, useEffect, useRef, useState } from "react";

export type ToastTone = "success" | "error" | "info";
export interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  detail?: string;
}

// Module-level mailbox so non-React code (axios interceptors, async fns)
// can call toast.error() without prop-drilling a context. Set by Provider.
type Publish = (t: Omit<ToastItem, "id">) => void;
let _publish: Publish | null = null;

export const toast = {
  success(title: string, detail?: string) { _publish?.({ tone: "success", title, detail }); },
  error(title: string, detail?: string)   { _publish?.({ tone: "error",   title, detail }); },
  info(title: string, detail?: string)    { _publish?.({ tone: "info",    title, detail }); },
};

const TONE_STYLE: Record<ToastTone, { bg: string; ink: string; border: string; ttlMs: number; icon: string }> = {
  success: { bg: "rgba(48,128,72,0.12)",  ink: "#1e4a2f", border: "rgba(48,128,72,0.45)",  ttlMs: 3500, icon: "✓" },
  error:   { bg: "rgba(199,46,46,0.10)",  ink: "#7a2a2a", border: "rgba(199,46,46,0.45)",  ttlMs: 7000, icon: "!" },
  info:    { bg: "rgba(0,30,60,0.08)",    ink: "#001E3C", border: "rgba(0,30,60,0.30)",    ttlMs: 4500, icon: "i" },
};

export const ToastContext = createContext<Publish>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(1);

  const publish: Publish = useCallback((t) => {
    const item: ToastItem = { id: nextIdRef.current++, ...t };
    setItems((prev) => [...prev, item]);
    const ttl = TONE_STYLE[item.tone].ttlMs;
    window.setTimeout(() => {
      setItems((prev) => prev.filter((x) => x.id !== item.id));
    }, ttl);
  }, []);

  useEffect(() => {
    _publish = publish;
    return () => { _publish = null; };
  }, [publish]);

  return (
    <ToastContext.Provider value={publish}>
      {children}
      {/* Render surface */}
      <div
        aria-live="polite"
        style={{
          position: "fixed",
          right: 20,
          bottom: 20,
          display: "flex",
          flexDirection: "column",
          gap: 10,
          zIndex: 9999,
          maxWidth: "min(420px, calc(100vw - 40px))",
          pointerEvents: "none",
        }}
      >
        {items.map((t) => {
          const s = TONE_STYLE[t.tone];
          return (
            <div
              key={t.id}
              style={{
                background: "#fff",
                borderLeft: `4px solid ${s.border}`,
                boxShadow: "0 8px 24px rgba(0,30,60,0.18)",
                borderRadius: 4,
                padding: "12px 14px",
                pointerEvents: "auto",
                animation: "toastIn 180ms ease-out",
              }}
            >
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <div
                  style={{
                    width: 22, height: 22, borderRadius: "50%",
                    background: s.bg, color: s.ink,
                    display: "grid", placeItems: "center",
                    fontWeight: 700, fontSize: 13, flexShrink: 0,
                  }}
                  aria-hidden="true"
                >
                  {s.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: "var(--color-navy, #001E3C)" }}>
                    {t.title}
                  </div>
                  {t.detail && (
                    <div style={{ fontSize: 13, color: "var(--color-muted, #6b6b6b)", marginTop: 2, wordBreak: "break-word" }}>
                      {t.detail}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setItems((prev) => prev.filter((x) => x.id !== t.id))}
                  aria-label="Dismiss"
                  style={{
                    background: "transparent", border: "none", cursor: "pointer",
                    color: "var(--color-muted, #6b6b6b)", fontSize: 16, padding: 2,
                    lineHeight: 1, flexShrink: 0,
                  }}
                >
                  ×
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
