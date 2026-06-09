import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { login, setAuth } from "../services/api";
import { wsClient } from "../services/websocket";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(username, password);
      setAuth(res.access_token, res.staff.role, res.staff.username);
      wsClient.start();
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      {/* LEFT — editorial hero */}
      <aside className="login-art">
        <div className="brand-mini">
          <div className="logo">S</div>
          <div>
            <div className="s">Smart Reception</div>
            <div className="n">Assistant</div>
          </div>
        </div>

        <div>
          <div className="hero-eyebrow">Welcome</div>
          <h1 className="hero-h">
            Hospitality, recognised<br />
            <em style={{ fontStyle: "italic" }}>at first glance</em>.
          </h1>
          <p className="ed" style={{ marginTop: 24 }}>
            Greet returning guests by name from the moment they enter the lobby —
            powered by computer vision, in real time.
          </p>
        </div>

        <div className="meta-row">
          <span>
            <b>v0.9</b> · Senior Project
          </span>
          <span>
            <b>AUL</b> · Computer & Communications Engineering
          </span>
        </div>
      </aside>

      {/* RIGHT — sign-in form */}
      <section className="login-form">
        <div className="login-form-inner">
          <div className="h">Staff sign-in</div>
          <div className="sub">Enter your reception credentials to continue.</div>

          {error && <div className="err">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="u">Username</label>
              <input
                id="u"
                type="text"
                autoComplete="username"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="p">Password</label>
              <input
                id="p"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary submit" disabled={loading}>
              <LogIn />
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="hint">
            Default admin: <b>admin / admin123</b>
          </div>
        </div>
      </section>
    </div>
  );
}
