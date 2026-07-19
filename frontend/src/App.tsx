import { NavLink, Route, Routes, useParams } from "react-router-dom";

import { useAuth } from "./auth";
import AnalyzePage from "./pages/AnalyzePage";
import AuditPage from "./pages/AuditPage";
import LoginPage from "./pages/LoginPage";
import UsersPage from "./pages/UsersPage";
import BackupOverviewPage from "./pages/BackupOverviewPage";
import BackupsPage from "./pages/BackupsPage";
import BlockedContactsPage from "./pages/BlockedContactsPage";
import ChatListPage from "./pages/ChatListPage";
import GpsPage from "./pages/GpsPage";
import GroupChatPage from "./pages/GroupChatPage";
import GroupsPage from "./pages/GroupsPage";
import HomePage from "./pages/HomePage";
import MarketplacePage from "./pages/MarketplacePage";
import PrivateChatPage from "./pages/PrivateChatPage";
import ProcessesPage from "./pages/ProcessesPage";
import ProcessResultsPage from "./pages/ProcessResultsPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import ProjectsPage from "./pages/ProjectsPage";
import StatusPage from "./pages/StatusPage";
import VerifyReportPage from "./pages/VerifyReportPage";
import type { Platform } from "./api/client";

function BackupNav() {
  const { platform, backupId } = useParams<{ platform: Platform; backupId: string }>();
  // the pattern also matches non-backup paths like /projects/<id>
  if (!platform || !backupId || (platform !== "ios" && platform !== "android")) return null;
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
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <p className="muted" style={{ padding: "2rem" }}>Loading…</p>;
  }
  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Forensic Wace</h1>
        <nav>
          <NavLink to="/" end>
            Select backup
          </NavLink>
          <NavLink to="/projects">Projects</NavLink>
          <NavLink to="/processes">AI processes</NavLink>
          <NavLink to="/verify">Verify report</NavLink>
          <NavLink to="/status">Analyzer status</NavLink>
          <NavLink to="/marketplace">Marketplace</NavLink>
          {user.role === "admin" && !user.auth_disabled && <NavLink to="/users">Users</NavLink>}
          {user.role === "admin" && <NavLink to="/audit">Audit trail</NavLink>}
          <Routes>
            <Route path="/:platform/:backupId/*" element={<BackupNav />} />
            <Route path="*" element={null} />
          </Routes>
        </nav>
        <div className="sidebar-user">
          <span>
            {user.username} <span className="muted">({user.role})</span>
          </span>
          {!user.auth_disabled && (
            <button className="button secondary" onClick={logout}>
              Sign out
            </button>
          )}
        </div>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
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
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </main>
    </div>
  );
}
