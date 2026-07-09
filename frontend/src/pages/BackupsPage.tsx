import { useNavigate, useParams } from "react-router-dom";

import { api, type Platform } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function BackupsPage() {
  const { platform } = useParams<{ platform: Platform }>();
  const navigate = useNavigate();
  const isIos = platform === "ios";

  const { data, error, loading } = useLoad<Record<string, unknown>[]>(
    async () => (isIos ? await api.listIosBackups() : await api.listAndroidBackups()) as unknown as Record<string, unknown>[],
    [platform],
  );

  const columns = isIos
    ? [
        { key: "udid", label: "UDID" },
        { key: "device_name", label: "Device" },
        { key: "ios_version", label: "iOS" },
        { key: "serial_number", label: "Serial" },
        { key: "backup_date", label: "Backup date" },
      ]
    : [
        { key: "folder", label: "Extraction folder" },
        { key: "db_file", label: "Database" },
        { key: "size_mb", label: "Size (MB)" },
        { key: "created_at", label: "Created" },
      ];

  return (
    <>
      <h2>{isIos ? "iOS" : "Android"} backups</h2>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <DataTable
          columns={columns}
          rows={data}
          onRowClick={(row) => navigate(`/${platform}/${encodeURIComponent(String(isIos ? row.udid : row.folder))}`)}
        />
      )}
    </>
  );
}
