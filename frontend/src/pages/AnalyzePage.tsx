import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, type InstalledAnalyzer, type Platform } from "../api/client";
import { ErrorBox, Loading } from "../components";
import { useLoad } from "../hooks";

const MESSAGE_TYPES = ["text", "image", "audio", "video", "gif", "location", "url", "file"];

function analyzerLabel(analyzer: InstalledAnalyzer): string {
  return analyzer.trust === "cloud" ? `${analyzer.name} ☁ cloud` : analyzer.name;
}

function MultiCheck({
  options,
  selected,
  onChange,
}: {
  options: { key: string; label: string }[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const toggle = (key: string) =>
    onChange(selected.includes(key) ? selected.filter((k) => k !== key) : [...selected, key]);
  return (
    <div className="row">
      {options.map((option) => (
        <label key={option.key}>
          <input type="checkbox" checked={selected.includes(option.key)} onChange={() => toggle(option.key)} />{" "}
          {option.label}
        </label>
      ))}
    </div>
  );
}

export default function AnalyzePage() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  const navigate = useNavigate();

  const chats = useLoad(() => api.chats(platform!, backupId!), [platform, backupId]);
  const groups = useLoad(() => api.groups(platform!, backupId!), [platform, backupId]);
  const installed = useLoad(() => api.listAnalyzers(), []);

  const available = (installed.data ?? []).filter((a) => a.enabled);
  const textAnalyzers = available.filter((a) => a.input === "text");
  const mediaAnalyzers = available.filter((a) => a.input !== "text");

  const [contacts, setContacts] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [received, setReceived] = useState(true);
  const [sent, setSent] = useState(true);
  const [messageTypes, setMessageTypes] = useState<string[]>(["text"]);
  const [analyzers, setAnalyzers] = useState<string[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const contactOptions = (chats.data ?? []).map((c) => String(c.PhoneNumber));
  const groupOptions = (groups.data ?? []).map((g) => String(g.Group_Name));

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.submitAnalysis({
        platform: platform!,
        backup_id: backupId!,
        date_from: dateFrom ? new Date(dateFrom).toISOString() : null,
        date_to: dateTo ? new Date(dateTo).toISOString() : null,
        received,
        sent,
        contacts,
        groups: selectedGroups,
        message_types: messageTypes,
        analyzers,
      });
      navigate("/processes");
    } catch (err) {
      setSubmitError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const nothingSelected = contacts.length === 0 && selectedGroups.length === 0;

  return (
    <>
      <h2>AI analysis</h2>
      <ErrorBox message={chats.error ?? groups.error ?? installed.error ?? submitError} />
      <Loading active={chats.loading || groups.loading || installed.loading} />

      <div className="card">
        <h3>Scope</h3>
        <div className="field">
          <label>Contacts</label>
          <select multiple size={5} value={contacts} onChange={(e) => setContacts(Array.from(e.target.selectedOptions, (o) => o.value))}>
            {contactOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Groups</label>
          <select
            multiple
            size={4}
            value={selectedGroups}
            onChange={(e) => setSelectedGroups(Array.from(e.target.selectedOptions, (o) => o.value))}
          >
            {groupOptions.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div className="row">
          <div className="field">
            <label>From</label>
            <input type="datetime-local" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="field">
            <label>To</label>
            <input type="datetime-local" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <label>
            <input type="checkbox" checked={received} onChange={(e) => setReceived(e.target.checked)} /> Received
          </label>
          <label>
            <input type="checkbox" checked={sent} onChange={(e) => setSent(e.target.checked)} /> Sent
          </label>
        </div>
        <div className="field">
          <label>Message types</label>
          <MultiCheck
            options={MESSAGE_TYPES.map((t) => ({ key: t, label: t }))}
            selected={messageTypes}
            onChange={setMessageTypes}
          />
        </div>
      </div>

      <div className="card">
        <h3>Analyzers</h3>
        {available.length === 0 && !installed.loading && (
          <p className="muted">No analyzers installed or enabled — check the Analyzer status page.</p>
        )}
        {textAnalyzers.length > 0 && (
          <div className="field">
            <label>Text analysis</label>
            <MultiCheck
              options={textAnalyzers.map((a) => ({ key: a.key, label: analyzerLabel(a) }))}
              selected={analyzers}
              onChange={setAnalyzers}
            />
          </div>
        )}
        {mediaAnalyzers.length > 0 && (
          <div className="field">
            <label>Media enrichment</label>
            <MultiCheck
              options={mediaAnalyzers.map((a) => ({ key: a.key, label: analyzerLabel(a) }))}
              selected={analyzers}
              onChange={setAnalyzers}
            />
          </div>
        )}
      </div>

      <button onClick={submit} disabled={submitting || nothingSelected || analyzers.length === 0}>
        {submitting ? "Starting…" : "Start analysis"}
      </button>
      {nothingSelected && <p className="muted">Select at least one contact or group.</p>}
    </>
  );
}
