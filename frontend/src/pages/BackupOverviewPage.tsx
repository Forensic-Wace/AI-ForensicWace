import { Link, useParams } from "react-router-dom";

import { api, exportUrl, type Platform } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function BackupOverviewPage() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  const { data, error, loading } = useLoad(() => api.backupDetail(platform!, backupId!), [platform, backupId]);

  return (
    <>
      <h2>Backup overview</h2>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <>
          {data.info && (
            <div className="card">
              <h3>{data.info.device_name ?? backupId}</h3>
              <p className="muted">
                iOS {data.info.ios_version} — {data.info.device_type} — serial {data.info.serial_number}
              </p>
            </div>
          )}
          {data.schema && !data.schema.error && (
            <div className="card">
              <h3>WhatsApp schema</h3>
              <p>
                <span className="badge ok">{data.schema.id}</span> {data.schema.display_name}
              </p>
              <p className="muted">
                {Object.entries(data.schema.capabilities ?? {}).map(([name, supported]) => (
                  <span key={name} className={`badge ${supported ? "ok" : "ko"}`} style={{ marginRight: "0.4rem" }}>
                    {name}
                  </span>
                ))}
              </p>
              {(data.schema.missing_optional_tables?.length ?? 0) > 0 && (
                <p className="muted">
                  Degraded support — missing optional tables: {data.schema.missing_optional_tables!.join(", ")}
                </p>
              )}
            </div>
          )}
          {data.schema?.error && (
            <div className="error">
              <b>Unknown WhatsApp schema.</b> {data.schema.error}
              <p className="muted">
                Please open a "WhatsApp schema support" issue on GitHub attaching the table inventory below
                (structure only, no data): user_version={data.schema.user_version},{" "}
                {Object.keys(data.schema.tables ?? {}).length} tables.
              </p>
              <pre className="mono" style={{ maxHeight: 200, overflow: "auto" }}>
                {JSON.stringify(data.schema.tables, null, 2)}
              </pre>
            </div>
          )}
          <div className="card">
            <h3>Evidence integrity</h3>
            <p>
              <b>SHA256</b> <span className="mono">{data.database.sha256}</span>
            </p>
            <p>
              <b>MD5</b> <span className="mono">{data.database.md5}</span>
            </p>
            <p>
              <b>Size</b> {data.database.size_mb} MB
            </p>
          </div>
          <div className="row">
            <Link className="button" to={`/${platform}/${encodeURIComponent(backupId!)}/chats`}>
              Chats
            </Link>
            <Link className="button" to={`/${platform}/${encodeURIComponent(backupId!)}/groups`}>
              Groups
            </Link>
            <Link className="button" to={`/${platform}/${encodeURIComponent(backupId!)}/gps`}>
              GPS locations
            </Link>
            {platform === "ios" && (
              <a className="button secondary" href={exportUrl(backupId!, "chat-list")}>
                Export chat list (signed PDF)
              </a>
            )}
          </div>
        </>
      )}
    </>
  );
}
