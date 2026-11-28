import { ArrowRight, Building2, LogOut } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, Navigate } from 'react-router';
import { AuthFrame } from '../components/auth-frame';
import { OrgMark } from '../components/org-mark';
import { ADMIN_PATH, AdminMark } from '../components/shell';
import { Button, Card, EmptyState, ErrorNote, Mono, SkeletonRows } from '../components/ui';
import { useOrganizations } from '../lib/org';
import { useSuperadmin } from '../lib/queries';
import { useSignOut } from '../lib/query-client';

function Choice({ to, mark, name, sub }: { to: string; mark: ReactNode; name: string; sub: ReactNode }) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-3 border-b border-line px-4 py-3 transition-colors duration-150 last:border-0 hover:bg-panel-2/60"
    >
      {mark}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{name}</span>
        {sub}
      </span>
      <ArrowRight className="size-4 text-muted transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-fg" />
    </Link>
  );
}

// The orgs of the signed-in officer. An officer with one org goes straight to it; the superadmin also gets the
// Superadmin entry, so the list stays.
export function OrganizationsPage() {
  const { data, isLoading, error } = useOrganizations();
  const superadmin = useSuperadmin();
  const signOut = useSignOut();
  if (data?.length === 1 && !superadmin.isLoading && !superadmin.data) return <Navigate to={`/${data[0].prefix}`} replace />;
  const loading = isLoading || superadmin.isLoading;
  return (
    <AuthFrame width="max-w-md">
      <h1 className="text-xl font-semibold tracking-tight">Choose an org</h1>
      <p className="mt-1.5 text-sm text-muted">The orgs where you have the officer role.</p>
      {error ? (
        <div className="mt-6">
          <ErrorNote error={error} />
        </div>
      ) : null}
      {superadmin.data ? (
        <Card className="mt-6 shadow-xs">
          <Choice to={ADMIN_PATH} mark={<AdminMark className="size-8" />} name="Superadmin" sub={<span className="block text-xs text-muted">Every org and the server</span>} />
        </Card>
      ) : null}
      <Card className={superadmin.data ? 'mt-3 shadow-xs' : 'mt-6 shadow-xs'}>
        {loading ? (
          <SkeletonRows rows={3} />
        ) : data?.length ? (
          data.map((org) => (
            <Choice key={org.id} to={`/${org.prefix}`} mark={<OrgMark name={org.name} className="size-8" />} name={org.name} sub={<Mono>{org.prefix}</Mono>} />
          ))
        ) : (
          <EmptyState icon={Building2} title="No orgs yet" />
        )}
      </Card>
      <div className="mt-4 flex justify-center">
        <Button variant="ghost" className="text-xs" onClick={signOut}>
          <LogOut className="size-3.5" /> Sign out
        </Button>
      </div>
    </AuthFrame>
  );
}
