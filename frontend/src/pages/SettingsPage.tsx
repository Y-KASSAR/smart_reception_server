import { FormEvent, useEffect, useState } from "react";
import { Pencil, Plus, Server, Trash2, Wrench, X } from "lucide-react";
import { api, currentRole, fetchSystemStatus, SystemStatus, SubsystemStatus } from "../services/api";
import { toast } from "../components/Toast/Toast";

interface ServiceRow {
  id: number;
  name: string;
  category: string;
  description: string | null;
  price: number | null;
  is_active: boolean;
  popularity_score: number;
}

type ServiceDraft = {
  name: string;
  category: string;
  description: string;
  price: string;          // text-input → parsed on submit
  popularity_score: string;
  is_active: boolean;
};

const EMPTY_DRAFT: ServiceDraft = {
  name: "", category: "spa", description: "", price: "0",
  popularity_score: "0.5", is_active: true,
};

export default function SettingsPage() {
  const [tab, setTab] = useState<"system" | "services">("system");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [services, setServices] = useState<ServiceRow[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<ServiceDraft>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const isAdmin = currentRole() === "admin" || currentRole() === "manager";

  async function loadServices() {
    try {
      const r = await api.get<ServiceRow[]>("/api/services/");
      setServices(r.data);
    } catch {}
  }

  useEffect(() => {
    fetchSystemStatus().then(setStatus).catch(() => {});
    loadServices();
  }, []);

  function openCreate() {
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
    setErr(null);
    setEditorOpen(true);
  }

  function openEdit(s: ServiceRow) {
    setEditingId(s.id);
    setDraft({
      name: s.name, category: s.category, description: s.description ?? "",
      price: String(s.price ?? 0), popularity_score: String(s.popularity_score),
      is_active: s.is_active,
    });
    setErr(null);
    setEditorOpen(true);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    const body: any = {
      name: draft.name.trim(),
      category: draft.category.trim(),
      description: draft.description.trim() || null,
      price: Number(draft.price) || 0,
      popularity_score: Math.max(0, Math.min(1, Number(draft.popularity_score) || 0)),
      is_active: draft.is_active,
    };
    try {
      if (editingId == null) {
        await api.post("/api/services/", body);
      } else {
        await api.put(`/api/services/${editingId}`, body);
      }
      setEditorOpen(false);
      await loadServices();
      toast.success(editingId == null ? "Service created" : "Service updated", draft.name);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? "Save failed.";
      setErr(msg);
      toast.error("Couldn't save service", msg);
    } finally {
      setBusy(false);
    }
  }

  async function remove(s: ServiceRow) {
    if (!window.confirm(`Delete "${s.name}" from the catalogue? This can't be undone.`)) return;
    setBusy(true);
    try {
      await api.delete(`/api/services/${s.id}`);
      await loadServices();
      toast.success("Service deleted", s.name);
    } catch (e: any) {
      toast.error("Delete failed", e?.response?.data?.detail ?? "Try again or check the logs.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">System</div>
        <h1 className="page-h1">Settings</h1>
        <p className="page-lead">
          Subsystem liveness and the catalogue of services used by the
          recommendation engine. Live threshold editing is on the roadmap.
        </p>
      </header>

      <div className="row" style={{ borderBottom: "1px solid var(--border-hairline)", marginBottom: 20 }}>
        <TabBtn active={tab === "system"} onClick={() => setTab("system")}><Server size={14} /> System</TabBtn>
        <TabBtn active={tab === "services"} onClick={() => setTab("services")}><Wrench size={14} /> Services Catalog</TabBtn>
      </div>

      {tab === "system" && (
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Liveness</div>
              <h3>Subsystem status</h3>
            </div>
          </div>
          {!status ? (
            <div className="panel-empty">Loading…</div>
          ) : (
            <table className="gtable">
              <thead>
                <tr>
                  <th>Subsystem</th>
                  <th>State</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {([
                  status.database,
                  status.recognition,
                  status.person_detection,
                  status.monitoring,
                  status.alert_pipeline,
                ] as SubsystemStatus[]).map((s) => (
                  <tr key={s.name}>
                    <td style={{ textTransform: "capitalize", fontWeight: 600 }}>{s.name.replace(/_/g, " ")}</td>
                    <td>
                      <span className={`chip ${s.ok ? "resolved" : "security"}`}>
                        <span className="d" />
                        {s.ok ? "Online" : "Degraded"}
                      </span>
                    </td>
                    <td className="muted t-mono" style={{ fontSize: 12 }}>{s.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="panel-body padded">
            <p className="t-caption">
              Threshold editing requires modifying <code>config.yaml</code> on the server and restarting it.
            </p>
          </div>
        </div>
      )}

      {tab === "services" && (
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Catalogue</div>
              <h3>Services <span className="t-caption tnum">· {services.length}</span></h3>
            </div>
            {isAdmin && (
              <button type="button" className="btn btn-gold btn-sm" onClick={openCreate}>
                <Plus size={14} /> New service
              </button>
            )}
          </div>
          {services.length === 0 ? (
            <div className="empty">
              <div className="h">No services configured</div>
              <div className="s">
                {isAdmin
                  ? <>Click <strong>New service</strong> to add the first one, or run <code>python scripts/seed_services.py</code> to bulk-seed.</>
                  : <>Ask an admin to add some.</>}
              </div>
            </div>
          ) : (
            <table className="gtable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th style={{ textAlign: "right" }}>Price</th>
                  <th style={{ textAlign: "right" }}>Popularity</th>
                  <th>Active</th>
                  {isAdmin && <th style={{ textAlign: "right" }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {services.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong>{s.name}</strong>
                      {s.description && <div className="t-caption" style={{ marginTop: 2 }}>{s.description}</div>}
                    </td>
                    <td><span className="nat">{s.category}</span></td>
                    <td className="tnum" style={{ textAlign: "right" }}>{s.price != null ? `$${s.price.toFixed(0)}` : "—"}</td>
                    <td className="tnum" style={{ textAlign: "right" }}>{s.popularity_score.toFixed(2)}</td>
                    <td>
                      <span className={`chip ${s.is_active ? "resolved" : "neutral"}`}>
                        <span className="d" />
                        {s.is_active ? "Yes" : "No"}
                      </span>
                    </td>
                    {isAdmin && (
                      <td style={{ textAlign: "right" }}>
                        <button
                          type="button" className="btn btn-ghost btn-sm"
                          onClick={() => openEdit(s)} disabled={busy}
                        >
                          <Pencil size={12} /> Edit
                        </button>
                        <button
                          type="button" className="btn btn-ghost btn-sm"
                          onClick={() => remove(s)} disabled={busy}
                          style={{ marginLeft: 4 }}
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* FR-2.11 — Create / Edit service modal (admin / manager only) */}
      {editorOpen && (
        <div
          onClick={() => !busy && setEditorOpen(false)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,20,40,0.55)",
            display: "grid", placeItems: "center", zIndex: 50,
          }}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={save}
            className="panel"
            style={{ width: "min(560px, 92vw)", maxHeight: "90vh", overflow: "auto" }}
          >
            <div className="panel-head">
              <div>
                <div className="eyebrow">{editingId == null ? "New" : "Edit"} service</div>
                <h3>{editingId == null ? "Add to catalogue" : draft.name || "Edit service"}</h3>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setEditorOpen(false)}
                disabled={busy}
              >
                <X size={14} />
              </button>
            </div>
            <div className="panel-body padded" style={{ display: "grid", gap: 12 }}>
              <Field label="Name *">
                <input
                  type="text" required value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </Field>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field label="Category *">
                  <select
                    value={draft.category}
                    onChange={(e) => setDraft({ ...draft, category: e.target.value })}
                  >
                    <option value="spa">spa</option>
                    <option value="dining">dining</option>
                    <option value="activities">activities</option>
                    <option value="room_service">room_service</option>
                  </select>
                </Field>
                <Field label="Price (USD)">
                  <input
                    type="number" min={0} step={1}
                    value={draft.price}
                    onChange={(e) => setDraft({ ...draft, price: e.target.value })}
                  />
                </Field>
              </div>
              <Field label="Description">
                <textarea
                  rows={2}
                  value={draft.description}
                  onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                />
              </Field>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Field label="Popularity (0.0 – 1.0)">
                  <input
                    type="number" min={0} max={1} step={0.05}
                    value={draft.popularity_score}
                    onChange={(e) => setDraft({ ...draft, popularity_score: e.target.value })}
                  />
                </Field>
                <label className="row" style={{ gap: 8, alignSelf: "end", paddingBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={draft.is_active}
                    onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
                  />
                  <span>Active in catalogue</span>
                </label>
              </div>

              {err && (
                <div style={{
                  padding: 10, borderRadius: 4, fontSize: 13,
                  background: "rgba(199,46,46,0.08)", color: "#7a2a2a",
                }}>{err}</div>
              )}

              <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
                <button type="button" className="btn btn-ghost" onClick={() => setEditorOpen(false)} disabled={busy}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-gold" disabled={busy || !draft.name.trim()}>
                  {busy ? "Saving…" : (editingId == null ? "Create service" : "Save changes")}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="form-field">
      <label>{label}</label>
      {children}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "10px 16px",
        background: "transparent", border: "none",
        borderBottom: active ? "2px solid var(--color-navy-900)" : "2px solid transparent",
        color: active ? "var(--fg-brand)" : "var(--fg-muted)",
        fontFamily: "inherit", fontSize: 13, fontWeight: active ? 600 : 500,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}
