import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <>
      <h2>Select a device backup</h2>
      <p className="muted">
        Backups are read from the extraction folders configured on the server (FW_DATA_DIR). Evidence databases are
        always opened read-only.
      </p>
      <div className="grid">
        <div className="card">
          <h3> iOS</h3>
          <p className="muted">Unencrypted iTunes-style backups (ChatStorage.sqlite + Manifest).</p>
          <Link className="button" to="/backups/ios">
            Browse iOS backups
          </Link>
        </div>
        <div className="card">
          <h3>🤖 Android</h3>
          <p className="muted">Extraction folders containing msgstore.db (and optional Media/).</p>
          <Link className="button" to="/backups/android">
            Browse Android backups
          </Link>
        </div>
        <div className="card">
          <h3>📁 Projects</h3>
          <p className="muted">Upload backups from the browser into a case project, stored on S3/MinIO.</p>
          <Link className="button" to="/projects">
            Manage projects
          </Link>
        </div>
      </div>
    </>
  );
}
