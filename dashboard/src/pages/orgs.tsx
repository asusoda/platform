import { ArrowRight } from 'lucide-react';
import { Link, Navigate } from 'react-router';
import { useOrganizations } from '../lib/org';
import { Card, Empty, ErrorNote, Loading } from '../components/ui';

export function OrganizationsPage() {
  const { data, isLoading, error } = useOrganizations();
  if (isLoading) return <Loading />;
  if (data?.length === 1) return <Navigate to={`/${data[0].prefix}`} replace />;
  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <h1 className="text-xl font-semibold">Choose an organization</h1>
      <p className="mt-1 text-sm text-muted">Organizations where you hold the officer role.</p>
      <div className="mt-6">{error ? <ErrorNote error={error} /> : null}</div>
      <Card className="mt-2">
        {data?.length ? (
          data.map((org) => (
            <Link
              key={org.id}
              to={`/${org.prefix}`}
              className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0 hover:bg-panel-2"
            >
              <span className="flex size-8 items-center justify-center rounded-lg bg-fg text-sm font-semibold text-bg uppercase">
                {org.name.slice(0, 1)}
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium">{org.name}</span>
                <span className="block font-mono text-xs text-muted">{org.prefix}</span>
              </span>
              <ArrowRight className="size-4 text-muted" />
            </Link>
          ))
        ) : (
          <Empty>No organizations yet. A superadmin creates one with flask --app main org create.</Empty>
        )}
      </Card>
    </div>
  );
}
