import { CheckCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { moduleLabel, NotificationItem } from '../components/notifications';
import { TabBar, useTabParam } from '../components/tabs';
import { Button, Card, EmptyState, ErrorNote, PageHeader, Select, ShowMore, SkeletonRows, useShowMore } from '../components/ui';
import { useCurrentOrg } from '../lib/org';
import { useNotificationChange, useNotifications } from '../lib/queries';

const TABS = [
  { id: 'open', label: 'Open' },
  { id: 'resolved', label: 'Resolved' },
] as const;

// Every current problem of the org. Resolve hides one until its message changes.
export function NotificationsPage() {
  const { prefix } = useCurrentOrg();
  const { data, isLoading, error } = useNotifications(prefix);
  const change = useNotificationChange(prefix);
  const [tab, setTab] = useTabParam(TABS);
  const [module, setModule] = useState('');
  const all = data?.notifications ?? [];
  const modules = useMemo(() => [...new Set(all.map((n) => n.module))], [all]);
  const shown = useMemo(
    () => all.filter((n) => Boolean(n.resolved_at) === (tab === 'resolved') && (!module || n.module === module)),
    [all, tab, module],
  );
  const page = useShowMore(shown, `${tab}:${module}`, 50);
  const counts = { open: data?.open ?? 0, resolved: all.length - (data?.open ?? 0) };

  return (
    <>
      <PageHeader
        title="Notifications"
        description="Problems that need an officer: failed alert runs, failed deploys and sources that could not be fetched."
        action={
          tab === 'open' && shown.length ? (
            <Button disabled={change.isPending} onClick={() => change.mutate({ action: 'resolve', ids: shown.map((n) => n.id) })}>
              <CheckCheck className="size-4" /> Resolve {module ? 'these' : 'all'}
            </Button>
          ) : null
        }
      />
      <TabBar
        label="Notifications"
        tabs={TABS}
        value={tab}
        onChange={setTab}
        extra={(id) => <span className="ml-1.5 text-xs text-muted tabular-nums">{counts[id]}</span>}
      />
      {error ? <ErrorNote error={error} /> : null}
      {change.error ? <ErrorNote error={change.error} /> : null}
      <Card>
        {modules.length > 1 ? (
          <div className="flex justify-end border-b border-line px-4 py-2.5">
            <Select value={module} onChange={(e) => setModule(e.target.value)} aria-label="Module" className="h-8 w-44! text-xs">
              <option value="">All modules</option>
              {modules.map((m) => (
                <option key={m} value={m}>
                  {moduleLabel(m)}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        {isLoading ? (
          <SkeletonRows rows={6} />
        ) : page.shown.length ? (
          <>
            <ul className="divide-y divide-line">
              {page.shown.map((n) => (
                <NotificationItem key={n.id} n={n} />
              ))}
            </ul>
            <ShowMore list={page} noun="notifications" />
          </>
        ) : (
          <EmptyState icon={CheckCheck} title={tab === 'open' ? 'Nothing needs attention' : 'Nothing resolved'}>
            {tab === 'open'
              ? 'New problems show here and on the bell at the top.'
              : 'A resolved notification shows here until its problem goes away.'}
          </EmptyState>
        )}
      </Card>
    </>
  );
}
