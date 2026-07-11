import { api } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function AuditPage() {
  const { data, error, loading, reload } = useLoad(() => api.listAudit(), []);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Audit trail</h2>
        <button onClick={reload} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      <p className="muted">
        Append-only record of operator actions (logins, uploads, analyses, exports, registry changes) — the
        chain-of-custody companion to the per-finding analyzer provenance.
      </p>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Operator</th>
              <th>Action</th>
              <th>Resource</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {data.map((entry) => (
              <tr key={entry.id}>
                <td className="mono">{entry.at}</td>
                <td>{entry.username ?? "—"}</td>
                <td>
                  <span className="badge busy">{entry.action}</span>
                </td>
                <td className="mono">{entry.resource ?? ""}</td>
                <td className="muted">{entry.detail ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
