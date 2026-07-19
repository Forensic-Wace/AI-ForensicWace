import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type CatalogEntry, type InstalledAnalyzer } from "../api/client";
import { useAuth } from "../auth";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

function TrustBadge({ trust }: { trust: "local" | "cloud" }) {
  return trust === "local" ? (
    <span className="badge ok" title="Evidence never leaves the deployment">
      local — no egress
    </span>
  ) : (
    <span className="badge ko" title="Evidence content is sent to an external service">
      cloud — evidence leaves
    </span>
  );
}

function EntryCard({
  entry,
  provisioner,
  isAdmin,
  onChanged,
}: {
  entry: CatalogEntry;
  provisioner: boolean;
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [endpoint, setEndpoint] = useState("");
  const [configText, setConfigText] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const install = async () => {
    setError(null);
    let config: Record<string, unknown> = {};
    if (configText.trim()) {
      try {
        const parsed: unknown = JSON.parse(configText);
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          setError('Config must be a JSON object, e.g. {"languages": ["eng"]}');
          return;
        }
        config = parsed as Record<string, unknown>;
      } catch {
        setError("Config must be valid JSON");
        return;
      }
    }
    setBusy(true);
    try {
      await api.installFromCatalog(entry.key, {
        endpoint: endpoint.trim() || undefined,
        config,
        consent,
      });
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const uninstall = async () => {
    if (!window.confirm(`Uninstall analyzer '${entry.key}'?`)) return;
    setError(null);
    try {
      await api.uninstallAnalyzer(entry.key);
      onChanged();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ marginBottom: 0 }}>
          {entry.name} <span className="muted">v{entry.version}</span>
        </h3>
        {entry.installed ? (
          <span className="badge ok">installed {entry.installed_version ? `v${entry.installed_version}` : ""}</span>
        ) : (
          isAdmin && (
            <button onClick={() => setOpen(!open)} disabled={busy}>
              {open ? "Cancel" : "Install"}
            </button>
          )
        )}
      </div>
      <p className="row" style={{ gap: "0.4rem" }}>
        <TrustBadge trust={entry.trust} />
        {entry.capabilities.map((c) => (
          <span key={c} className="badge busy">
            {c}
          </span>
        ))}
        <span className="badge busy">{entry.input}</span>
        {entry.gpu && <span className="badge busy">GPU</span>}
      </p>
      {entry.description && <p className="muted">{entry.description}</p>}
      <p className="mono muted" style={{ fontSize: "0.8rem", wordBreak: "break-all" }}>
        {entry.image}
      </p>
      {entry.publisher && (
        <p className="muted">
          Publisher: {entry.publisher}
          {/^https?:\/\//i.test(entry.homepage) && (
            <>
              {" · "}
              <a href={entry.homepage} target="_blank" rel="noreferrer">
                homepage
              </a>
            </>
          )}
        </p>
      )}
      <ErrorBox message={error} />
      {entry.installed && isAdmin && (
        <button className="button secondary" onClick={uninstall}>
          Uninstall
        </button>
      )}
      {open && !entry.installed && (
        <div className="card" style={{ marginTop: "0.5rem" }}>
          {!provisioner && (
            <div className="field">
              <label>Endpoint of the running container</label>
              <input
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder={`http://host:${entry.port}`}
              />
              <p className="muted">
                No runtime provisioner is configured: start the pinned image yourself and point the platform at
                it.
              </p>
            </div>
          )}
          <div className="field">
            <label>Config (JSON{Object.keys(entry.config_schema ?? {}).length ? ", see schema below" : ""})</label>
            <textarea value={configText} onChange={(e) => setConfigText(e.target.value)} placeholder="{}" rows={3} />
            {Object.keys(entry.config_schema ?? {}).length > 0 && (
              <pre className="mono muted" style={{ fontSize: "0.75rem", overflowX: "auto" }}>
                {JSON.stringify(entry.config_schema, null, 2)}
              </pre>
            )}
          </div>
          {entry.trust === "cloud" && (
            <label className="error" style={{ display: "block", padding: "0.5rem" }}>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> I
              understand that evidence content (messages, media) will be sent to an external cloud service by
              this analyzer, and I am authorized to allow it for this deployment.
            </label>
          )}
          <button onClick={install} disabled={busy || (entry.trust === "cloud" && !consent)}>
            {busy ? "Installing…" : `Install ${entry.key}`}
          </button>
        </div>
      )}
    </div>
  );
}

function InstalledTable({
  analyzers,
  isAdmin,
  onChanged,
}: {
  analyzers: InstalledAnalyzer[];
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <>
      <ErrorBox message={error} />
      <table>
        <thead>
          <tr>
            <th>Key</th>
            <th>Type</th>
            <th>Version</th>
            <th>Trust</th>
            <th>Capabilities</th>
            <th>Enabled</th>
            {isAdmin && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {analyzers.map((a) => (
            <tr key={a.key}>
              <td className="mono">{a.key}</td>
              <td>{a.type}</td>
              <td>{a.version}</td>
              <td>
                <TrustBadge trust={a.trust} />
              </td>
              <td>{a.capabilities.join(", ")}</td>
              <td>{a.enabled ? "✅" : "—"}</td>
              {isAdmin && (
                <td className="row">
                  <button
                    className="button secondary"
                    onClick={() => run(() => api.updateAnalyzer(a.key, { enabled: !a.enabled }))}
                  >
                    {a.enabled ? "Disable" : "Enable"}
                  </button>
                  {a.type === "http" && (
                    <button
                      className="button secondary"
                      onClick={() => {
                        if (window.confirm(`Uninstall analyzer '${a.key}'?`)) run(() => api.uninstallAnalyzer(a.key));
                      }}
                    >
                      Uninstall
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function RegisterByEndpoint({ onChanged }: { onChanged: () => void }) {
  const [endpoint, setEndpoint] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const register = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.registerAnalyzer(endpoint.trim(), {}, consent);
      setEndpoint("");
      setConsent(false);
      onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h3>Register by endpoint</h3>
      <p className="muted">
        Bring your own fw-analyzer/1 container: its manifest is fetched from the endpoint and is authoritative.
      </p>
      <ErrorBox message={error} />
      <div className="row">
        <input
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="http://my-analyzer:9300"
          style={{ flex: 1 }}
        />
        <button onClick={register} disabled={!endpoint.trim() || busy}>
          {busy ? "Registering…" : "Register"}
        </button>
      </div>
      <label className="muted">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> If the
        container declares trust=cloud, I consent to evidence content being sent to its external service
        (required only for cloud analyzers).
      </label>
    </div>
  );
}

export default function MarketplacePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const catalog = useLoad(() => api.marketplaceCatalog(), []);
  const installed = useLoad(() => api.listAnalyzers(), []);

  const reload = () => {
    catalog.reload();
    installed.reload();
  };

  const catalogUnavailable = catalog.error !== null;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Analyzer marketplace</h2>
        {catalog.data &&
          (catalog.data.verified ? (
            <span className="badge ok" title="Catalog signature verified against the pinned public key">
              catalog verified
            </span>
          ) : (
            <span className="badge ko" title="Set FW_CATALOG_PUBLIC_KEY to require a valid signature">
              catalog NOT verified
            </span>
          ))}
      </div>
      <p className="muted">
        Install analyzers from the signed catalog — images are pinned to sha256 digests. Health of installed
        analyzers lives on the <Link to="/status">status page</Link>.
      </p>
      <Loading active={catalog.loading && !catalog.data} />
      {catalogUnavailable && (
        <div className="card">
          <p className="muted">Catalog unavailable: {catalog.error}</p>
        </div>
      )}
      {catalog.data && (
        <div className="grid">
          {catalog.data.entries.map((entry) => (
            <EntryCard
              key={entry.key}
              entry={entry}
              provisioner={catalog.data!.provisioner}
              isAdmin={isAdmin}
              onChanged={reload}
            />
          ))}
        </div>
      )}

      <h3 style={{ marginTop: "1.5rem" }}>Installed analyzers</h3>
      <ErrorBox message={installed.error} />
      <Loading active={installed.loading && !installed.data} />
      {installed.data && <InstalledTable analyzers={installed.data} isAdmin={isAdmin} onChanged={reload} />}

      {isAdmin && <RegisterByEndpoint onChanged={reload} />}
    </>
  );
}
