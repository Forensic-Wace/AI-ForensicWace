import { useEffect } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

function StatusBadge({ status }: { status: string | null }) {
  if (status === "Finish") return <span className="badge ok">finished</span>;
  if (status === "Error") return <span className="badge ko">error</span>;
  return <span className="badge busy">{status ?? "unknown"}</span>;
}

export default function ProcessesPage() {
  const { data, error, loading, reload } = useLoad(() => api.listAnalyses(), []);

  // Live progress: poll while any process is still running.
  useEffect(() => {
    if (!data?.some((p) => p.status === "Started" || p.status === "Analyzing")) return;
    const timer = setInterval(reload, 3000);
    return () => clearInterval(timer);
  }, [data, reload]);

  const active = data?.filter((p) => p.status === "Started" || p.status === "Analyzing").length ?? 0;
  const finished = data?.filter((p) => p.status === "Finish").length ?? 0;

  return (
    <>
      <h2>AI analysis processes</h2>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <>
          <div className="counters card">
            <div className="stat">
              <b>{data.length}</b>
              <span className="muted">total</span>
            </div>
            <div className="stat">
              <b>{active}</b>
              <span className="muted">active</span>
            </div>
            <div className="stat">
              <b>{finished}</b>
              <span className="muted">finished</span>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Process</th>
                <th>Platform</th>
                <th>Backup</th>
                <th>Status</th>
                <th>Details</th>
                <th>Started</th>
                <th>Results</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.process_id}>
                  <td className="mono">{p.process_id.slice(0, 8)}…</td>
                  <td>{p.platform}</td>
                  <td>{p.backup_id}</td>
                  <td>
                    <StatusBadge status={p.status} />
                  </td>
                  <td>{p.details}</td>
                  <td>{p.start_time}</td>
                  <td>
                    <Link to={`/processes/${p.process_id}`}>View results</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
