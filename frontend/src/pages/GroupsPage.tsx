import { useNavigate, useParams } from "react-router-dom";

import { api, exportUrl, type Platform } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function GroupsPage() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  const navigate = useNavigate();
  const { data, error, loading } = useLoad(() => api.groups(platform!, backupId!), [platform, backupId]);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Groups</h2>
        {platform === "ios" && (
          <a className="button secondary" href={exportUrl(backupId!, "group-list")}>
            Export signed PDF
          </a>
        )}
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <DataTable
          columns={[
            { key: "Group_Name", label: "Group" },
            { key: "Message_Date", label: "Last message" },
            { key: "Number_of_Messages", label: "Messages" },
            ...(platform === "ios" ? [{ key: "Is_muted", label: "Notifications" }] : []),
          ]}
          rows={data}
          render={{
            Is_muted: (row) =>
              row.Is_muted != null ? <span className="badge ko">muted</span> : <span className="badge ok">enabled</span>,
          }}
          onRowClick={
            platform === "ios"
              ? (row) =>
                  navigate(
                    `/ios/${encodeURIComponent(backupId!)}/groups/${encodeURIComponent(String(row.Group_Name))}`,
                  )
              : undefined
          }
        />
      )}
      {platform === "android" && (
        <p className="muted">Group message browsing for Android arrives with the schema registry phase.</p>
      )}
    </>
  );
}
