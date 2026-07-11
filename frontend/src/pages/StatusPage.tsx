import { api } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function StatusPage() {
  const { data, error, loading, reload } = useLoad(() => api.analyzersStatus(), []);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Analyzer status</h2>
        <button onClick={reload} disabled={loading}>
          {loading ? "Checking…" : "Re-check"}
        </button>
      </div>
      <p className="muted">
        Live health check of every installed analyzer — built-ins (configured through FW_* environment variables) and
        analyzers registered at runtime through the registry API.
      </p>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <table>
          <thead>
            <tr>
              <th>Analyzer</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.name}>
                <td>{s.name}</td>
                <td>{s.available ? <span className="badge ok">available</span> : <span className="badge ko">unavailable</span>}</td>
                <td className="muted">{s.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
