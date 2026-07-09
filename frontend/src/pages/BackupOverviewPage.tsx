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
