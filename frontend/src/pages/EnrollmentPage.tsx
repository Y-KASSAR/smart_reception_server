import { ChangeEvent, FormEvent, useRef, useState } from "react";
import { Camera, CheckCircle2, FileImage, Trash2, Upload } from "lucide-react";
import { api } from "../services/api";
import { useWebSocketEvent } from "../hooks/useWebSocket";
import { toast } from "../components/Toast/Toast";

type EnrollmentSource = "live" | "upload";

// Multi-angle enrollment guidance. FaceNet embeddings drift with head pose, so
// capturing a few angles (stored as separate per-guest embeddings, matched
// best-of) is what lets a guest be recognised when turned ~30–45° from the
// camera. Each capture slot nudges the next pose.
const POSE_GUIDE = [
  "Look straight at the camera",
  "Turn your head ~30° to the LEFT",
  "Turn your head ~30° to the RIGHT",
  "Tilt your head slightly UP",
  "Tilt your head slightly DOWN",
];

interface CaptureFrame {
  frame_b64: string;
  preview_b64?: string;
  quality?: number;
}

interface LiveFeedPayload {
  event: "live_feed";
  camera_id: string;
  frame_b64: string;
  detections: any[];
  ts: string;
}

/**
 * Enrollment page.
 *
 * Captures three quick face shots **from the Pi's lobby camera feed** (via the
 * /ws live_feed WebSocket event) rather than the laptop's webcam. This matches
 * the SDD's reception-desk enrollment flow and removes the laptop-webcam
 * dependency entirely.
 */
export default function EnrollmentPage() {
  const { last: liveFeed, connected } = useWebSocketEvent<LiveFeedPayload>("live_feed");

  const [source, setSource] = useState<EnrollmentSource>("live");
  const [frames, setFrames] = useState<CaptureFrame[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [result, setResult] = useState<{ guestId: number; stored: number; failed: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [nationality, setNationality] = useState("");
  const [language, setLanguage] = useState("en");
  const [vip, setVip] = useState(false);
  const [notes, setNotes] = useState("");
  const [consent, setConsent] = useState(false);

  const hasLiveFrame = !!liveFeed?.frame_b64;

  async function _runCapture(b64: string): Promise<void> {
    setCapturing(true);
    try {
      const { data } = await api.post("/api/enrollment/capture", { frame_b64: b64 });
      if (!data?.face_detected) {
        toast.error("No face detected", data?.message ?? "Try a clearer, front-facing shot.");
        return;
      }
      setFrames((prev) => [
        ...prev,
        { frame_b64: b64, preview_b64: data.face_image_b64, quality: data.quality_score },
      ]);
      toast.success("Face captured", `Quality ${(data.quality_score ?? 0).toFixed(2)}`);
    } catch (e) {
      toast.error("Capture failed", "Check backend logs.");
    } finally {
      setCapturing(false);
    }
  }

  async function captureFrame() {
    if (!hasLiveFrame) {
      toast.error(
        connected ? "No camera frame yet" : "WebSocket offline",
        connected ? "Wait a moment for the Pi to push one." : "Refresh the page."
      );
      return;
    }
    await _runCapture(liveFeed!.frame_b64);
  }

  // Strip the "data:image/...;base64," prefix that FileReader adds — the
  // backend expects raw base64 only.
  function _stripDataUrlPrefix(dataUrl: string): string {
    const comma = dataUrl.indexOf(",");
    return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  }

  async function onFilePicked(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Wrong file type", "Pick an image (JPEG / PNG / WebP).");
      e.target.value = "";
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error("Image too large", "Max 8 MB. Try a smaller scan.");
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = String(reader.result || "");
      const b64 = _stripDataUrlPrefix(dataUrl);
      setUploadPreview(dataUrl);
      await _runCapture(b64);
    };
    reader.readAsDataURL(file);
    e.target.value = ""; // allow re-picking the same file
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!consent) {
      toast.error("Consent required", "Tick the consent box to register facial biometric data (GDPR / NFR-2.10).");
      return;
    }
    if (frames.length === 0) {
      toast.error("No face captured", "Add at least one face image before submitting.");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post("/api/enrollment/complete", {
        guest: {
          full_name: fullName,
          email: email || null,
          phone: phone || null,
          nationality: nationality || null,
          language_preference: language,
          vip_status: vip,
          notes: notes || null,
        },
        face_images_b64: frames.map((f) => f.frame_b64),
        consent_given: true,
      });
      setResult({
        guestId: data.guest.id,
        stored: data.embeddings_stored,
        failed: data.embeddings_failed,
      });
      setFrames([]);
      toast.success(
        `Enrolled guest #${data.guest.id}`,
        `${data.embeddings_stored} embedding${data.embeddings_stored !== 1 ? "s" : ""} stored.`
      );
    } catch (e: any) {
      toast.error("Enrollment failed", e?.response?.data?.detail ?? "Check backend logs.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div className="page-eyebrow">Records</div>
        <h1 className="page-h1">New enrollment</h1>
        <p className="page-lead">
          Capture a few face shots <strong>at different head angles</strong> from the
          lobby camera, confirm consent, and register the guest's profile so they're
          recognised — even when turned ~30–45° — on their next visit.
        </p>
      </header>

      <div className="grid-2col">
        {/* Face capture (live OR upload) */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Step 1</div>
              <h3>Face capture</h3>
            </div>
            <div className="right t-caption tnum">{frames.length}/5</div>
          </div>

          {/* Source tabs */}
          <div
            className="row"
            style={{
              gap: 0,
              borderBottom: "1px solid var(--border-hairline)",
              padding: "0 14px",
            }}
          >
            {(
              [
                { key: "live",   label: "Live capture", icon: Camera },
                { key: "upload", label: "Upload photo", icon: FileImage },
              ] as const
            ).map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setSource(t.key)}
                className="btn"
                style={{
                  background: "transparent",
                  border: "none",
                  borderBottom: source === t.key ? "2px solid var(--color-gold)" : "2px solid transparent",
                  borderRadius: 0,
                  padding: "10px 14px",
                  fontWeight: source === t.key ? 600 : 400,
                  color: source === t.key ? "var(--color-navy)" : "var(--color-muted)",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <t.icon size={13} />
                {t.label}
              </button>
            ))}
          </div>

          <div style={{ padding: 14 }}>
            {source === "live" ? (
              <>
                <div className="feed" style={{ aspectRatio: "16 / 10" }}>
                  {hasLiveFrame ? (
                    <img
                      src={`data:image/jpeg;base64,${liveFeed!.frame_b64}`}
                      alt="Lobby camera live feed"
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "contain",
                        position: "absolute",
                        inset: 0,
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        position: "absolute",
                        inset: 0,
                        display: "grid",
                        placeItems: "center",
                        color: "rgba(251,248,242,0.5)",
                        fontSize: 13,
                        padding: 16,
                        textAlign: "center",
                      }}
                    >
                      {connected
                        ? "Waiting for lobby camera frames…"
                        : "WebSocket offline — refresh page"}
                    </div>
                  )}
                  <div className="feed-overlay-top">
                    <span className="feed-cam-label">
                      {liveFeed?.camera_id ?? "lobby_main"}
                    </span>
                    <span className="feed-time">
                      {liveFeed?.ts
                        ? new Date(liveFeed.ts).toLocaleTimeString()
                        : "--:--:--"}
                    </span>
                  </div>
                </div>

                {frames.length < 5 && (
                  <div
                    className="row"
                    style={{
                      gap: 8,
                      marginTop: 14,
                      padding: "8px 12px",
                      background: "var(--color-assistance-bg)",
                      border: "1px solid var(--color-assistance-tint)",
                      borderRadius: 4,
                      fontSize: 13,
                    }}
                  >
                    <Camera size={14} />
                    <span>
                      <strong>Pose {frames.length + 1}/5:</strong>{" "}
                      {POSE_GUIDE[frames.length]}
                    </span>
                  </div>
                )}

                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!hasLiveFrame || capturing || frames.length >= 5}
                  onClick={captureFrame}
                  style={{
                    marginTop: 10,
                    width: "100%",
                    justifyContent: "center",
                    padding: 12,
                  }}
                >
                  <Camera />
                  {capturing
                    ? "Analysing…"
                    : frames.length >= 5
                    ? "All 5 poses captured"
                    : `Capture pose ${frames.length + 1}/5 — ${POSE_GUIDE[frames.length]}`}
                </button>
              </>
            ) : (
              <>
                {/* Upload mode: drop zone + file picker */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    aspectRatio: "16 / 10",
                    border: "1.5px dashed var(--border-hairline)",
                    borderRadius: 6,
                    background: uploadPreview ? "var(--bg-canvas)" : "rgba(0,30,60,0.02)",
                    cursor: "pointer",
                    position: "relative",
                    overflow: "hidden",
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  {uploadPreview ? (
                    <img
                      src={uploadPreview}
                      alt="Uploaded photo preview"
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "contain",
                      }}
                    />
                  ) : (
                    <div style={{ textAlign: "center", padding: 20, color: "var(--color-muted)" }}>
                      <Upload size={26} style={{ marginBottom: 8 }} />
                      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-navy)" }}>
                        Drop a passport / ID photo here
                      </div>
                      <div style={{ fontSize: 12, marginTop: 4 }}>
                        or click to browse · JPEG / PNG · max 8 MB
                      </div>
                    </div>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  style={{ display: "none" }}
                  onChange={onFilePicked}
                />
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={capturing || frames.length >= 5}
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    marginTop: 14,
                    width: "100%",
                    justifyContent: "center",
                    padding: 12,
                  }}
                >
                  <Upload size={14} />
                  {capturing
                    ? "Analysing…"
                    : `Choose photo (${frames.length}/5 captured)`}
                </button>
                <div className="t-caption" style={{ marginTop: 8, color: "var(--color-muted)", fontSize: 12 }}>
                  Tip: for best results add several photos at different head angles
                  (front, ¾ left, ¾ right). Each is stored separately and matched
                  best-of, so the guest is recognised even when turned.
                </div>
              </>
            )}

            {frames.length > 0 && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 10,
                  marginTop: 14,
                }}
              >
                {frames.map((f, i) => (
                  <div key={i} style={{ position: "relative" }}>
                    <img
                      src={`data:image/jpeg;base64,${f.preview_b64 ?? f.frame_b64}`}
                      alt={`capture-${i}`}
                      style={{
                        width: "100%",
                        height: 90,
                        objectFit: "cover",
                        borderRadius: 4,
                        border: "1px solid var(--border-hairline)",
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setFrames(frames.filter((_, j) => j !== i))}
                      className="btn btn-ghost btn-sm"
                      style={{
                        position: "absolute",
                        top: 4,
                        right: 4,
                        padding: 4,
                        background: "rgba(255,255,255,0.8)",
                      }}
                      title="Discard"
                    >
                      <Trash2 size={12} />
                    </button>
                    <div
                      className="t-caption"
                      style={{ textAlign: "center", marginTop: 4, lineHeight: 1.3 }}
                    >
                      <div style={{ fontSize: 11 }}>{POSE_GUIDE[i] ?? `Pose ${i + 1}`}</div>
                      <div className="tnum" style={{ color: "var(--color-muted)" }}>
                        q={f.quality?.toFixed(2) ?? "—"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Profile form */}
        <form onSubmit={handleSubmit} className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">Step 2</div>
              <h3>Guest profile</h3>
            </div>
          </div>
          <div className="panel-body padded">
            <Field
              label="Full name *"
              value={fullName}
              onChange={setFullName}
              required
            />
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
            />
            <Field label="Phone" value={phone} onChange={setPhone} />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
              }}
            >
              <Field
                label="Nationality (2-letter)"
                value={nationality}
                onChange={setNationality}
                maxLength={2}
              />
              <Field label="Language" value={language} onChange={setLanguage} />
            </div>

            <label
              className="row"
              style={{ gap: 8, fontSize: 13, marginBottom: 14, marginTop: 4 }}
            >
              <input
                type="checkbox"
                checked={vip}
                onChange={(e) => setVip(e.target.checked)}
              />
              <span>VIP guest</span>
            </label>

            <div className="form-field">
              <label>Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
              />
            </div>

            <label
              className="row"
              style={{
                alignItems: "flex-start",
                gap: 8,
                fontSize: 13,
                padding: 10,
                background: "var(--color-assistance-bg)",
                border: "1px solid var(--color-assistance-tint)",
                borderRadius: 4,
                marginBottom: 14,
              }}
            >
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                style={{ marginTop: 3 }}
              />
              <span>
                I confirm the guest has given <strong>explicit consent</strong>{" "}
                to capture and store their facial biometric data for
                identification purposes (NFR-2.10 / GDPR Art. 9).
              </span>
            </label>

            {result && (
              <div
                className="row"
                style={{
                  gap: 8,
                  padding: 10,
                  marginBottom: 14,
                  background: "var(--color-resolved-bg)",
                  border: "1px solid var(--color-resolved-tint)",
                  borderRadius: 4,
                  color: "var(--color-resolved-ink)",
                  fontSize: 13,
                }}
              >
                <CheckCircle2 size={16} />
                Enrolled guest #{result.guestId} — stored {result.stored}{" "}
                embedding{result.stored !== 1 ? "s" : ""} ({result.failed}{" "}
                failed).
              </div>
            )}

            <button
              type="submit"
              className="btn btn-gold"
              disabled={
                submitting ||
                !fullName ||
                !consent ||
                frames.length === 0
              }
              style={{ width: "100%", justifyContent: "center", padding: 12 }}
            >
              {submitting ? "Enrolling…" : "Complete enrollment"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  maxLength?: number;
}) {
  return (
    <div className="form-field">
      <label>{label}</label>
      <input
        type={type}
        required={required}
        value={value}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
