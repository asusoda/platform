import { ArrowRight, Building2, LogOut } from 'lucide-react';
import { Link, Navigate, useNavigate } from 'react-router';
import { AuthFrame } from '../components/auth-frame';
import { OrgMark } from '../components/org-mark';
import { Button, Card, EmptyState, ErrorNote, Mono, SkeletonRows } from '../components/ui';
import { tokens } from '../lib/auth';
import { useOrganizations } from '../lib/org';

export function OrganizationsPage() {
  const { data, isLoading, error } = useOrganizations();
  const navigate = useNavigate();
  if (data?.length === 1) return <Navigate to={`/${data[0].prefix}`} replace />;
  return (
    <AuthFrame width="max-w-md">
      <h1 className="text-xl font-semibold tracking-tight">Choose an org</h1>
      <p className="mt-1.5 text-sm text-muted">The orgs where you have the officer role.</p>
      {error ? (
        <div className="mt-6">
          <ErrorNote error={error} />
        </div>
      ) : null}
      <Card className="mt-6 shadow-xs">
        {isLoading ? (
          <SkeletonRows rows={3} />
        ) : data?.length ? (
          data.map((org) => (
            <Link
              key={org.id}
              to={`/${org.prefix}`}
              className="group flex items-center gap-3 border-b border-line px-4 py-3 transition-colors duration-150 last:border-0 hover:bg-panel-2/60"
            >
              <OrgMark name={org.name} className="size-8" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{org.name}</span>
                <Mono>{org.prefix}</Mono>
              </span>
              <ArrowRight className="size-4 text-muted transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-fg" />
            </Link>
          ))
        ) : (
          <EmptyState icon={Building2} title="No orgs yet">
            A superadmin adds one with <Mono>flask --app main org create</Mono>.
          </EmptyState>
        )}
      </Card>
      <div className="mt-4 flex justify-center">
        <Button
          variant="ghost"
          className="text-xs"
          onClick={() => {
            tokens.clear();
            navigate('/login');
          }}
        >
          <LogOut className="size-3.5" /> Sign out
        </Button>
      </div>
    </AuthFrame>
  );
}
