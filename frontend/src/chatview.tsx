import { mediaUrl } from "./api/client";

type Row = Record<string, unknown>;

// iOS ZMESSAGETYPE codes (mirrors forensicwace_core.constants.IosMessageType)
const IOS_TYPE_LABEL: Record<number, string> = {
  1: "📷 Image",
  2: "🎬 Video",
  3: "🎤 Voice message",
  4: "👤 Contact card",
  5: "📍 Position",
  6: "👥 Group event",
  7: "🔗 Link",
  8: "📄 File",
  11: "🖼️ GIF",
  14: "🗑️ Message deleted by the sender",
  15: "💟 Sticker",
  38: "📷 One-time image",
  39: "🎬 One-time video",
  46: "📊 Poll",
};

export const IOS_TYPE_FILTERS = [
  "images",
  "videos",
  "audios",
  "contacts",
  "positions",
  "urls",
  "files",
  "gifs",
  "stickers",
];

// Android numeric message_type → label (text handled separately)
const ANDROID_TYPE_LABEL: Record<number, string> = {
  1: "📷 Image",
  42: "📷 Image",
  2: "🎤 Audio",
  3: "🎬 Video",
  43: "🎬 Video",
  13: "🖼️ GIF",
  5: "📍 Position",
  6: "👥 Group event",
  7: "🔗 Link",
  9: "📄 File",
};

function gpsLink(row: Row): string {
  return `https://www.google.com/maps?q=${row.latitude},${row.longitude}`;
}

export function IosBubble({ row, backupId }: { row: Row; backupId: string }) {
  const isOwner = row.user == null;
  const type = Number(row.ZMESSAGETYPE ?? 0);
  const mediaPath = String(row.mediaPath ?? "");

  return (
    <div className={`bubble ${isOwner ? "owner" : "contact"}`}>
      {!isOwner && (
        <span className="sender">
          {String(row.contactName ?? row.vcardContactName ?? row.ZPARTNERNAME ?? row.user)} ({String(row.user)})
        </span>
      )}
      {type === 0 && <span>{String(row.text ?? "")}</span>}
      {type !== 0 && <span>{IOS_TYPE_LABEL[type] ?? `Message type ${type}`}</span>}
      {(type === 1 || type === 15) && mediaPath && (
        <img src={mediaUrl(backupId, { relativePath: mediaPath })} alt="attachment" loading="lazy" />
      )}
      {type === 4 && row.contactName != null && <span> — {String(row.contactName)}</span>}
      {type === 5 && (
        <a href={gpsLink(row)} target="_blank" rel="noreferrer">
          {" "}
          {String(row.latitude)}, {String(row.longitude)}
        </a>
      )}
      <span className="meta">{String(row.receiveDateTime ?? "")} UTC</span>
    </div>
  );
}

export function AndroidBubble({ row }: { row: Row }) {
  const isOwner = Boolean(row.from_me);
  const type = Number(row.message_type ?? 0);
  return (
    <div className={`bubble ${isOwner ? "owner" : "contact"}`}>
      {type === 0 ? (
        <span>{String(row.text_data ?? "")}</span>
      ) : (
        <span>{ANDROID_TYPE_LABEL[type] ?? `Message type ${type}`}</span>
      )}
      <span className="meta">{String(row.readable_timestamp ?? "")}</span>
    </div>
  );
}
