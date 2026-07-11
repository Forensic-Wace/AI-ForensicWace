import { useState } from "react";

import { api, type UserAccount } from "../api/client";
import { useAuth } from "../auth";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function UsersPage() {
  const { user: me } = useAuth();
  const { data, error, loading, reload } = useLoad(() => api.listUsers(), []);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("analyst");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await action();
      reload();
    } catch (err) {
      setActionError(String(err));
    }
  };

  const create = async () => {
    setBusy(true);
    await run(async () => {
      await api.createUser(username.trim(), password, role);
      setUsername("");
      setPassword("");
    });
    setBusy(false);
  };

  const resetPassword = (account: UserAccount) => {
    const next = window.prompt(`New password for '${account.username}' (min 8 characters):`);
    if (!next) return;
    run(() => api.updateUser(account.id, { password: next }));
  };

  return (
    <>
      <h2>Users</h2>
      <p className="muted">
        Operator accounts. Accounts are disabled, never deleted — their id stays on findings and uploads (chain of
        custody). Disabling an account or resetting its password revokes every open session.
      </p>
      <ErrorBox message={actionError} />
      <div className="card">
        <h3>New account</h3>
        <div className="row">
          <div className="field">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Password (min 8)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="field">
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="analyst">analyst</option>
              <option value="admin">admin</option>
            </select>
          </div>
        </div>
        <button onClick={create} disabled={!username.trim() || password.length < 8 || busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </div>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Status</th>
              <th>Last login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((account) => (
              <tr key={account.id}>
                <td>
                  {account.username}
                  {account.id === me?.id && <span className="muted"> (you)</span>}
                </td>
                <td>
                  <select
                    value={account.role}
                    disabled={account.id === me?.id}
                    onChange={(e) => run(() => api.updateUser(account.id, { role: e.target.value }))}
                  >
                    <option value="analyst">analyst</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td>
                  {account.is_active ? <span className="badge ok">active</span> : <span className="badge ko">disabled</span>}
                </td>
                <td>{account.last_login ?? "—"}</td>
                <td className="row">
                  <button className="button secondary" onClick={() => resetPassword(account)}>
                    Reset password
                  </button>
                  {account.id !== me?.id && (
                    <button
                      className="button secondary"
                      onClick={() => run(() => api.updateUser(account.id, { is_active: !account.is_active }))}
                    >
                      {account.is_active ? "Disable" : "Enable"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
