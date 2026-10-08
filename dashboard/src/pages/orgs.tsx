import { ArrowRight, Building2 } from 'lucide-react';
import { Link, Navigate } from 'react-router';
import { Logo } from '../components/logo';
import { OrgMark } from '../components/org-mark';
import { Card, EmptyState, ErrorNote, Mono, SkeletonRows } from '../components/ui';
import { useOrganizations } from '../lib/org';

export function OrganizationsPage() {
  const { data, isLoading, error } = useOrganizations();
  if (data?.length === 1) return <Navigate to={`/${data[0].prefix}`} replace />;
  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <div className="flex items-center gap-2 text-sm font-medium tracking-tight">
        <Logo className="size-5" />
        Platform
      </div>
      <h1 className="mt-8 text-2xl font-semibold tracking-tight">Choose an organization</h1>
      <p className="mt-1.5 text-sm text-muted">Organizations where you hold the officer role.</p>
      {error ? (
        <div className="mt-6">
          <ErrorNote error={error} />
        </div>
      ) : null}
      <Card className="mt-6">
        {isLoading ? (
          <SkeletonRows rows={3} />
        ) : data?.length ? (
          data.map((org) => (
            <Link
              key={org.id}
              to={`/${org.prefix}`}
              className="group flex items-center gap-3 border-b border-line px-4 py-3 transition-colors last:border-0 hover:bg-panel-2/50"
            >
              <OrgMark name={org.name} className="size-8" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{org.name}</span>
                <Mono>{org.prefix}</Mono>
              </span>
              <ArrowRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5" />
            </Link>
          ))
        ) : (
          <EmptyState icon={Building2} title="No organizations yet">
            A superadmin creates one with <Mono>flask --app main org create</Mono>.
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
