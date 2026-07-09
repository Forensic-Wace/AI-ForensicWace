import { useParams } from "react-router-dom";

import { api, exportUrl, type Platform } from "../api/client";
import { DataTable, ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

export default function GpsPage() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  const { data, error, loading } = useLoad(() => api.gpsLocations(platform!, backupId!), [platform, backupId]);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>GPS locations</h2>
        {platform === "ios" && (
          <a className="button secondary" href={exportUrl(backupId!, "gps-locations")}>
            Export signed PDF
          </a>
        )}
      </div>
      <ErrorBox message={error} />
      <Loading active={loading} />
      {data && (
        <DataTable
          columns={[
            { key: "Sender", label: "Sender" },
            { key: "Receiver", label: "Receiver" },
            { key: "MessageDate", label: "Date" },
            { key: "Latitude", label: "Latitude" },
            { key: "Longitude", label: "Longitude" },
            { key: "map", label: "Map" },
          ]}
          rows={data}
          render={{
            map: (row) => (
              <a href={`https://www.google.com/maps?q=${row.Latitude},${row.Longitude}`} target="_blank" rel="noreferrer">
                Open map
              </a>
            ),
          }}
        />
      )}
    </>
  );
}
