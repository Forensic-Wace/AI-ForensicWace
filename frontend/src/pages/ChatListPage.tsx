import { useNavigate, useParams } from "react-router-dom";

import { api, exportUrl, type Platform } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function ChatListPage() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  const navigate = useNavigate();
  const { data, error, loading } = useLoad(() => api.chats(platform!, backupId!), [platform, backupId]);

  const columns =
    platform === "ios"
      ? [
          { key: "Contact", label: "Contact" },
          { key: "UserName", label: "Username" },
          { key: "PhoneNumber", label: "Phone number" },
          { key: "NumberOfMessages", label: "Messages" },
          { key: "MessageDate", label: "Last message" },
        ]
      : [
          { key: "PhoneNumber", label: "Phone number" },
          { key: "NumberOfMessages", label: "Messages" },
          { key: "MessageDate", label: "Last message" },
        ];

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Chats</h2>
        {platform === "ios" && (
          <a className="button secondary" href={exportUrl(backupId!, "chat-list")}>
            Export signed PDF
          </a>
        )}
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <DataTable
          columns={columns}
          rows={data}
          onRowClick={(row) =>
            navigate(`/${platform}/${encodeURIComponent(backupId!)}/chats/${encodeURIComponent(String(row.PhoneNumber))}`)
          }
        />
      )}
    </>
  );
}
