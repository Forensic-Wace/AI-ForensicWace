import { useState } from "react";
import { useParams } from "react-router-dom";

import { api, exportUrl, type Platform } from "../api/client";
import { AndroidBubble, IOS_TYPE_FILTERS, IosBubble } from "../chatview";
import { Counters, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function PrivateChatPage() {
  const { platform, backupId, phone } = useParams<{ platform: Platform; backupId: string; phone: string }>();
  const [typeFilter, setTypeFilter] = useState("");

  const { data, error, loading } = useLoad(
    () => api.privateChat(platform!, backupId!, phone!, typeFilter || undefined),
    [platform, backupId, phone, typeFilter],
  );

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Chat with {phone}</h2>
        <div className="row">
          {platform === "ios" && (
            <>
              <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                <option value="">All message types</option>
                {IOS_TYPE_FILTERS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
              <a className="button secondary" href={exportUrl(backupId!, `chats/${encodeURIComponent(phone!)}`)}>
                Export signed PDF
              </a>
            </>
          )}
        </div>
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <>
          <Counters counters={data.counters} />
          <div className="chat">
            {data.messages.map((row, i) =>
              platform === "ios" ? (
                <IosBubble key={i} row={row} backupId={backupId!} />
              ) : (
                <AndroidBubble key={i} row={row} />
              ),
            )}
          </div>
        </>
      )}
    </>
  );
}
