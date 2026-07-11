import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, uploadProjectBackup, type Platform, type ProjectBackup, type ProjectDetail } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

function BackupStatusBadge({ backup }: { backup: ProjectBackup }) {
  if (backup.status === "error") return <span className="badge ko">error</span>;
  if (backup.status === "stored") return <span className="badge ok">stored</span>;
  return <span className="badge busy">{backup.status}</span>;
}

function UploadCard({ projectId, onUploaded }: { projectId: string; onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [platform, setPlatform] = useState<Platform>("android");
  const [identifier, setIdentifier] = useState("");
  const [autoHydrate, setAutoHydrate] = useState(true);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pickFile = (picked: File | null) => {
    setFile(picked);
    if (picked && !identifier) setIdentifier(picked.name.replace(/\.zip$/i, ""));
  };

  const submit = async () => {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      await uploadProjectBackup(
        projectId,
        { file, platform, identifier: identifier.trim() || undefined, autoHydrate },
        setProgress,
      );
      setFile(null);
      setIdentifier("");
      onUploaded();
    } catch (err) {
      setError(String(err));
    } finally {
      setProgress(null);
    }
  };

  const uploading = progress !== null;
  return (
    <div className="card">
      <h3>Upload a backup</h3>
      <p className="muted">
        ZIP the extraction folder (Android: msgstore.db + optional Media/ — iOS: the whole iTunes-style backup
        folder with Manifest.db/Manifest.plist) and upload it. It is mirrored to object storage and, if requested,
        immediately available as a working copy.
      </p>
      <ErrorBox message={error} />
      <div className="row">
        <div className="field">
          <label>Platform</label>
          <select value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} disabled={uploading}>
            <option value="android">Android</option>
            <option value="ios">iOS</option>
          </select>
        </div>
        <div className="field">
          <label>Identifier (folder / UDID)</label>
          <input
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="e.g. case42-phone1"
            disabled={uploading}
          />
        </div>
        <div className="field">
          <label>Archive (.zip)</label>
          <input type="file" accept=".zip" onChange={(e) => pickFile(e.target.files?.[0] ?? null)} disabled={uploading} />
        </div>
      </div>
      <div className="row">
        <label>
          <input type="checkbox" checked={autoHydrate} onChange={(e) => setAutoHydrate(e.target.checked)} disabled={uploading} />{" "}
          Materialize a local working copy right away
        </label>
        <button onClick={submit} disabled={!file || uploading}>
          {uploading ? `Uploading… ${progress}%` : "Upload"}
        </button>
      </div>
      {uploading && (
        <div className="progress">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}

function SharingCard({ project, onChanged }: { project: ProjectDetail; onChanged: () => void }) {
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);

  const share = async () => {
    setError(null);
    try {
      await api.addProjectMember(project.id, username.trim());
      setUsername("");
      onChanged();
    } catch (err) {
      setError(String(err));
    }
  };

  const unshare = async (userId: number) => {
    setError(null);
    try {
      await api.removeProjectMember(project.id, userId);
      onChanged();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="card">
      <h3>Sharing</h3>
      <p className="muted">
        {project.owner ? `Case owner: ${project.owner}. ` : ""}
        Only the owner, shared operators and admins can see this case.
      </p>
      <ErrorBox message={error} />
      {project.members.length > 0 && (
        <ul>
          {project.members.map((m) => (
            <li key={m.user_id} className="row">
              <span>{m.username ?? `user #${m.user_id}`}</span>
              {project.can_manage && (
                <button className="button secondary" onClick={() => unshare(m.user_id)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {project.can_manage && (
        <div className="row">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username to share with"
          />
          <button onClick={share} disabled={!username.trim()}>
            Share
          </button>
        </div>
      )}
    </div>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, error, loading, reload } = useLoad(() => api.projectDetail(projectId!), [projectId]);

  // Live progress: poll while any backup is still being mirrored or hydrated.
  useEffect(() => {
    if (!data?.backups.some((b) => b.status === "processing" || b.status === "hydrating")) return;
    const timer = setInterval(reload, 3000);
    return () => clearInterval(timer);
  }, [data, reload]);

  const run = async (action: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await action();
      reload();
    } catch (err) {
      setActionError(String(err));
    }
  };

  const deleteProject = () => {
    if (!window.confirm("Delete this project and all its backups from object storage? Local working copies are kept.")) return;
    run(async () => {
      await api.deleteProject(projectId!);
      navigate("/projects");
    });
  };

  const deleteBackup = (backup: ProjectBackup) => {
    if (!window.confirm(`Remove backup '${backup.identifier}' from object storage?`)) return;
    const purgeLocal =
      backup.hydrated && window.confirm("Also delete the local working copy? (Cancel keeps it on disk)");
    run(() => api.deleteProjectBackup(projectId!, backup.id, purgeLocal));
  };

  return (
    <>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 style={{ marginBottom: 0 }}>Project: {data.name}</h2>
            {data.can_manage && (
              <button className="button secondary" onClick={deleteProject}>
                Delete project
              </button>
            )}
          </div>
          {data.description && <p className="muted">{data.description}</p>}
          <ErrorBox message={actionError} />

          <UploadCard projectId={data.id} onUploaded={reload} />
          <SharingCard project={data} onChanged={reload} />

          <h3>Backups</h3>
          {data.backups.length === 0 && <p className="muted">No backups uploaded yet.</p>}
          {data.backups.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Identifier</th>
                  <th>Platform</th>
                  <th>Status</th>
                  <th>Size</th>
                  <th>Files</th>
                  <th>Working copy</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.backups.map((backup) => (
                  <tr key={backup.id}>
                    <td>
                      {backup.hydrated && backup.status === "stored" ? (
                        <Link to={`/${backup.platform}/${encodeURIComponent(backup.identifier)}`}>
                          {backup.identifier}
                        </Link>
                      ) : (
                        backup.identifier
                      )}
                    </td>
                    <td>{backup.platform}</td>
                    <td>
                      <BackupStatusBadge backup={backup} />
                      {backup.detail && <div className="muted">{backup.detail}</div>}
                    </td>
                    <td>{formatBytes(backup.size_bytes)}</td>
                    <td>{backup.file_count}</td>
                    <td>{backup.hydrated ? "✅ on disk" : "☁️ storage only"}</td>
                    <td className="row">
                      {backup.status === "stored" && !backup.hydrated && (
                        <button onClick={() => run(() => api.hydrateProjectBackup(projectId!, backup.id))}>
                          Hydrate
                        </button>
                      )}
                      <button className="button secondary" onClick={() => deleteBackup(backup)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </>
  );
}
