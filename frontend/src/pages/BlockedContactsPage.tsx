import { useParams } from "react-router-dom";

import { api, exportUrl } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function BlockedContactsPage() {
  const { backupId } = useParams<{ backupId: string }>();
  const { data, error, loading } = useLoad(() => api.blockedContacts(backupId!), [backupId]);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Blocked contacts</h2>
        <a className="button secondary" href={exportUrl(backupId!, "blocked-contacts")}>
          Export signed PDF
        </a>
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <DataTable
          columns={[
            { key: "Name", label: "Name" },
            { key: "PhoneNumber", label: "Phone number" },
          ]}
          rows={data}
        />
      )}
    </>
  );
}
