import { useState } from "react";

import { api } from "../api/client";
import { ErrorBox } from "../components";

export default function VerifyReportPage() {
  const [report, setReport] = useState<File | null>(null);
  const [token, setToken] = useState<File | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!report || !token) return;
    setBusy(true);
    setError(null);
    setVerified(null);
    try {
      const result = await api.verifyReport(report, token);
      setVerified(result.verified);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Verify a signed report</h2>
      <p className="muted">
        Upload a generated PDF report together with its RFC 3161 timestamp token (.tsr) to verify integrity and
        generation time.
      </p>
      <ErrorBox message={error} />
      <div className="card">
        <div className="field">
          <label>PDF report</label>
          <input type="file" accept=".pdf" onChange={(e) => setReport(e.target.files?.[0] ?? null)} />
        </div>
        <div className="field">
          <label>Timestamp token (.tsr)</label>
          <input type="file" accept=".tsr" onChange={(e) => setToken(e.target.files?.[0] ?? null)} />
        </div>
        <button onClick={submit} disabled={!report || !token || busy}>
          {busy ? "Verifying…" : "Verify"}
        </button>
      </div>
      {verified === true && <div className="card">✅ <b>Report is authentic</b> — signature and content match.</div>}
      {verified === false && (
        <div className="error">❌ Verification FAILED — the report or its token has been altered.</div>
      )}
    </>
  );
}
