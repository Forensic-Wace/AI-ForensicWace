import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { data, error, loading } = useLoad(() => api.listProjects(), []);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    setCreateError(null);
    try {
      const project = await api.createProject(name.trim(), description.trim());
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setCreateError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Projects</h2>
      <p className="muted">
        A project groups the backups of a case. Backups uploaded here are stored durably on the configured object
        storage (S3/MinIO) and materialized as working copies for extraction and analysis.
      </p>
      <div className="card">
        <h3>New project</h3>
        <ErrorBox message={createError} />
        <div className="row">
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Case 42" />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Description</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes about the case"
            />
          </div>
        </div>
        <button onClick={create} disabled={!name.trim() || busy}>
          {busy ? "Creating…" : "Create project"}
        </button>
      </div>
      <ErrorBox message={error} />
      <Loading active={loading && !data} />
      {data && (
        <DataTable
          columns={[
            { key: "name", label: "Name" },
            { key: "description", label: "Description" },
            { key: "backup_count", label: "Backups" },
            { key: "created_at", label: "Created" },
          ]}
          rows={data as unknown as Record<string, unknown>[]}
          onRowClick={(row) => navigate(`/projects/${row.id}`)}
        />
      )}
    </>
  );
}
