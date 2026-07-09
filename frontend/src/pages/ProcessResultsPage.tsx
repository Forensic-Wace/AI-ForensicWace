import { useParams } from "react-router-dom";

import { api } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function ProcessResultsPage() {
  const { processId } = useParams<{ processId: string }>();
  const process = useLoad(() => api.analysis(processId!), [processId]);
  const results = useLoad(() => api.analysisResults(processId!), [processId]);

  return (
    <>
      <h2>Analysis results</h2>
      <ErrorBox message={process.error ?? results.error} />
      <Loading active={process.loading || results.loading} />
      {process.data && (
        <div className="card">
          <p>
            <b>Process</b> <span className="mono">{process.data.process_id}</span>
          </p>
          <p>
            <b>Status</b> {process.data.status} — {process.data.details}
          </p>
          <p>
            <b>Analyzers</b> {process.data.analyzers.join(", ") || "—"}
          </p>
        </div>
      )}
      {results.data && results.data.length === 0 && <p className="muted">No findings stored for this process.</p>}
      {results.data?.map((result) => (
        <div className="card" key={result.msg_id + String(result.date)}>
          <p className="muted">
            Message {result.msg_id} — {result.date}
          </p>
          <p>{result.text}</p>
          {result.piis.length > 0 && (
            <p>
              <b>PII:</b>{" "}
              {result.piis.map((f, i) => (
                <span key={i} className="badge busy" style={{ marginRight: "0.4rem" }}>
                  {f.type}: {f.value} ({f.source})
                </span>
              ))}
            </p>
          )}
          {result.passwords.length > 0 && (
            <p>
              <b>Passwords:</b>{" "}
              {result.passwords.map((f, i) => (
                <span key={i} className="badge ko" style={{ marginRight: "0.4rem" }}>
                  {f.value} ({f.source})
                </span>
              ))}
            </p>
          )}
        </div>
      ))}
    </>
  );
}
