import { NavLink, Route, Routes, useParams } from "react-router-dom";

import AnalyzePage from "./pages/AnalyzePage";
import BackupOverviewPage from "./pages/BackupOverviewPage";
import BackupsPage from "./pages/BackupsPage";
import BlockedContactsPage from "./pages/BlockedContactsPage";
import ChatListPage from "./pages/ChatListPage";
import GpsPage from "./pages/GpsPage";
import GroupChatPage from "./pages/GroupChatPage";
import GroupsPage from "./pages/GroupsPage";
import HomePage from "./pages/HomePage";
import PrivateChatPage from "./pages/PrivateChatPage";
import ProcessesPage from "./pages/ProcessesPage";
import ProcessResultsPage from "./pages/ProcessResultsPage";
import StatusPage from "./pages/StatusPage";
import VerifyReportPage from "./pages/VerifyReportPage";
import type { Platform } from "./api/client";

function BackupNav() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  if (!platform || !backupId) return null;
  const base = `/${platform}/${encodeURIComponent(backupId)}`;
  return (
    <>
      <div className="section">Backup: {backupId}</div>
      <NavLink to={base} end>
        Overview
      </NavLink>
      <NavLink to={`${base}/chats`}>Chats</NavLink>
      <NavLink to={`${base}/groups`}>Groups</NavLink>
      <NavLink to={`${base}/gps`}>GPS locations</NavLink>
      {platform === "ios" && <NavLink to={`${base}/blocked`}>Blocked contacts</NavLink>}
      <NavLink to={`${base}/analyze`}>AI analysis</NavLink>
    </>
  );
}

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Forensic Wace</h1>
        <nav>
          <NavLink to="/" end>
            Select backup
          </NavLink>
          <NavLink to="/processes">AI processes</NavLink>
          <NavLink to="/verify">Verify report</NavLink>
          <NavLink to="/status">Analyzer status</NavLink>
          <Routes>
            <Route path="/:platform/:backupId/*" element={<BackupNav />} />
            <Route path="*" element={null} />
          </Routes>
        </nav>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/backups/:platform" element={<BackupsPage />} />
          <Route path="/:platform/:backupId" element={<BackupOverviewPage />} />
          <Route path="/:platform/:backupId/chats" element={<ChatListPage />} />
          <Route path="/:platform/:backupId/chats/:phone" element={<PrivateChatPage />} />
          <Route path="/:platform/:backupId/groups" element={<GroupsPage />} />
          <Route path="/ios/:backupId/groups/:groupName" element={<GroupChatPage />} />
          <Route path="/:platform/:backupId/gps" element={<GpsPage />} />
          <Route path="/ios/:backupId/blocked" element={<BlockedContactsPage />} />
          <Route path="/:platform/:backupId/analyze" element={<AnalyzePage />} />
          <Route path="/processes" element={<ProcessesPage />} />
          <Route path="/processes/:processId" element={<ProcessResultsPage />} />
          <Route path="/verify" element={<VerifyReportPage />} />
          <Route path="/status" element={<StatusPage />} />
        </Routes>
      </main>
    </div>
  );
}
