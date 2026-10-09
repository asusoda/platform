import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router';
import { Shell } from './components/shell';
import { tokens } from './lib/auth';
import { AuthCallbackPage } from './pages/auth-callback';
import { LoginPage } from './pages/login';
import { MemberStorePage } from './pages/member-store';
import { MemberLoginPage } from './pages/member-store/login';
import { OrganizationsPage } from './pages/orgs';
import { PAGES, pageElement, REDIRECTS } from './pages/registry';

function SignedIn({ children }: { children: ReactNode }) {
  return tokens.access() ? children : <Navigate to="/login" replace />;
}

// The org pages and redirects come from pages/registry.tsx.
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth" element={<AuthCallbackPage />} />
      <Route path="/store/:prefix" element={<MemberStorePage />} />
      <Route path="/store/:prefix/login" element={<MemberLoginPage />} />
      <Route path="/" element={<SignedIn><OrganizationsPage /></SignedIn>} />
      <Route path="/:org" element={<SignedIn><Shell /></SignedIn>}>
        {PAGES.map((p) =>
          p.path ? (
            <Route key={p.path} path={p.path} element={pageElement(p)} />
          ) : (
            <Route key="index" index element={pageElement(p)} />
          ),
        )}
        {REDIRECTS.map((r) => (
          <Route key={r.path} path={r.path} element={<Navigate to={r.to} replace />} />
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
