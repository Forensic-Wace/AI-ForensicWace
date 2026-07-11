import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useAuth } from "../auth";
import { ErrorBox } from "../components";

export default function LoginPage() {
  const { refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ssoAvailable, setSsoAvailable] = useState(false);

  useEffect(() => {
    api
      .authProviders()
      .then((p) => setSsoAvailable(p.oidc))
      .catch(() => setSsoAvailable(false));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(username, password);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="card login-card" onSubmit={submit}>
        <h1>Forensic Wace</h1>
        <p className="muted">Sign in to access the evidence workspace.</p>
        <ErrorBox message={error} />
        <div className="field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
        </div>
        <div className="field">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <button type="submit" disabled={!username || !password || busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {ssoAvailable && (
          <>
            <p className="muted" style={{ textAlign: "center", margin: "0.5rem 0" }}>
              or
            </p>
            <a className="button secondary" href="/api/v1/auth/oidc/login" style={{ textAlign: "center" }}>
              Sign in with SSO
            </a>
          </>
        )}
      </form>
    </div>
  );
}
