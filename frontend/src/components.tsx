import type { ReactNode } from "react";

export function ErrorBox({ message }: { message: string | null }) {
  return message ? <div className="error">{message}</div> : null;
}

export function Loading({ active }: { active: boolean }) {
  return active ? <p className="muted">Loading…</p> : null;
}

/** Generic data table over the raw row dicts returned by the API. */
export function DataTable({
  columns,
  rows,
  onRowClick,
  render,
}: {
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
  onRowClick?: (row: Record<string, unknown>) => void;
  render?: Partial<Record<string, (row: Record<string, unknown>) => ReactNode>>;
}) {
  if (rows.length === 0) return <p className="muted">No data.</p>;
  return (
    <table>
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className={onRowClick ? "clickable" : ""} onClick={() => onRowClick?.(row)}>
            {columns.map((c) => (
              <td key={c.key}>{render?.[c.key] ? render[c.key]!(row) : String(row[c.key] ?? "—")}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Counters({ counters }: { counters: Record<string, number | string | null> }) {
  const entries = Object.entries(counters).filter(([, v]) => v !== null);
  if (entries.length === 0) return null;
  return (
    <div className="counters card">
      {entries.map(([key, value]) => (
        <div className="stat" key={key}>
          <b>{String(value)}</b>
          <span className="muted">{key}</span>
        </div>
      ))}
    </div>
  );
}
