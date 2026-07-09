import { useState } from "react";
import { useParams } from "react-router-dom";

import { api, exportUrl } from "../api/client";
import { IOS_TYPE_FILTERS, IosBubble } from "../chatview";
import { Counters, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function GroupChatPage() {
  const { backupId, groupName } = useParams<{ backupId: string; groupName: string }>();
  const [typeFilter, setTypeFilter] = useState("");

  const { data, error, loading } = useLoad(
    () => api.groupChat(backupId!, groupName!, typeFilter || undefined),
    [backupId, groupName, typeFilter],
  );

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Group: {groupName}</h2>
        <div className="row">
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">All message types</option>
            {IOS_TYPE_FILTERS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
          <a className="button secondary" href={exportUrl(backupId!, `groups/${encodeURIComponent(groupName!)}`)}>
            Export signed PDF
          </a>
        </div>
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <>
          <Counters counters={data.counters} />
          <div className="chat">
            {data.messages.map((row, i) => (
              <IosBubble key={i} row={row} backupId={backupId!} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
