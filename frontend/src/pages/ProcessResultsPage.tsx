import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, subscribeAnalysisEvents, type Process } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

function Progress({ process }: { process: Process }) {
  const done = process.analyzed_messages + process.failed_messages;
  const pct = process.total_messages > 0 ? Math.round((done / process.total_messages) * 100) : 0;
  return (
    <div className="card">
      <p>
        <b>Status</b> {process.status} — {process.details}
      </p>
      {process.total_messages > 0 && (
        <div style={{ background: "#e8edf1", borderRadius: 6, overflow: "hidden", height: 10 }}>
          <div style={{ width: `${pct}%`, background: "var(--accent)", height: "100%" }} />
        </div>
      )}
      <p className="muted">
        {process.analyzed_messages} analyzed / {process.total_messages} total
        {process.failed_messages > 0 && (
          <>
            {" — "}
            <span className="badge ko">{process.failed_messages} failed (dead-letter queue)</span>
          </>
        )}
      </p>
    </div>
  );
}

export default function ProcessResultsPage() {
  const { processId } = useParams<{ processId: string }>();
  const process = useLoad(() => api.analysis(processId!), [processId]);
  const results = useLoad(() => api.analysisResults(processId!), [processId]);
  const [live, setLive] = useState<Process | null>(null);

  const current = live ?? process.data;
  const running = current != null && current.status !== "Finish" && current.status !== "Error";

  // Live updates while the analysis runs; reload the findings when it ends.
  useEffect(() => {
    if (!running) return;
    return subscribeAnalysisEvents(processId!, setLive, results.reload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processId, running]);

  return (
    <>
      <h2>Analysis results</h2>
      <ErrorBox message={process.error ?? results.error} />
      <Loading active={process.loading || results.loading} />
      {current && (
        <>
          <div className="card">
            <p>
              <b>Process</b> <span className="mono">{current.process_id}</span>
            </p>
            <p>
              <b>Analyzers</b> {current.analyzers.join(", ") || "—"}
            </p>
          </div>
          <Progress process={current} />
        </>
      )}
      {!running && results.data && results.data.length === 0 && (
        <p className="muted">No findings stored for this process.</p>
      )}
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
                <span
                  key={i}
                  className="badge busy"
                  style={{ marginRight: "0.4rem" }}
                  title={f.analyzer_version ? `${f.source} v${f.analyzer_version}${f.analyzer_digest ? ` (${f.analyzer_digest})` : ""}` : f.source}
                >
                  {f.type}: {f.value} ({f.source})
                </span>
              ))}
            </p>
          )}
          {result.passwords.length > 0 && (
            <p>
              <b>Passwords:</b>{" "}
              {result.passwords.map((f, i) => (
                <span
                  key={i}
                  className="badge ko"
                  style={{ marginRight: "0.4rem" }}
                  title={f.analyzer_version ? `${f.source} v${f.analyzer_version}${f.analyzer_digest ? ` (${f.analyzer_digest})` : ""}` : f.source}
                >
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
