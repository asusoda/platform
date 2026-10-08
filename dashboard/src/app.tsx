import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router';
import { Shell } from './components/shell';
import { tokens } from './lib/auth';
import { ActivityPage } from './pages/activity';
import { AdminPage } from './pages/admin';
import { AgentsPage } from './pages/agents';
import { AlertsPage } from './pages/alerts';
import { AppsPage } from './pages/apps';
import { AuthCallbackPage } from './pages/auth-callback';
import { CalendarPage } from './pages/calendar';
import { ComputePage } from './pages/compute';
import { KnowledgePage } from './pages/knowledge';
import { LeetCodePage } from './pages/leetcode';
import { LoginPage } from './pages/login';
import { OrganizationsPage } from './pages/orgs';
import { OverviewPage } from './pages/overview';
import { PointsPage } from './pages/points';
import { SettingsPage } from './pages/settings';
import { StorePage } from './pages/store';
import { TokensPage } from './pages/tokens';

function SignedIn({ children }: { children: ReactNode }) {
  return tokens.access() ? children : <Navigate to="/login" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth" element={<AuthCallbackPage />} />
      <Route path="/" element={<SignedIn><OrganizationsPage /></SignedIn>} />
      <Route path="/:org" element={<SignedIn><Shell /></SignedIn>}>
        <Route index element={<OverviewPage />} />
        <Route path="points" element={<PointsPage />} />
        <Route path="store" element={<StorePage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="leetcode" element={<LeetCodePage />} />
        <Route path="compute" element={<ComputePage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="apps" element={<AppsPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="ci" element={<Navigate to="../activity?tab=ci" replace />} />
        <Route path="tokens" element={<TokensPage />} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
