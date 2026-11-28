import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ArrowUpRight, History } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Badge,
  Card,
  cx,
  Dot,
  EmptyState,
  ErrorNote,
  Segmented,
  Select,
  ShowMore,
  SkeletonRows,
  useShowMore,
} from '../../components/ui';
import {
  fromAudit,
  fromCi,
  fromDeliveries,
  fromKnowledgeRuns,
  fromNotifications,
  mergeTimeline,
  TIMELINE_KINDS,
  type TimelineKind,
  type TimelineRow,
} from '../../lib/activity';
import { api } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import { moduleLabel } from '../../lib/modules';
import { useCurrentOrg } from '../../lib/org';
import { useCi, useNotifications } from '../../lib/queries';
import type { AuditEntry, DeliveryList, KnowledgeRun, Notification } from '../../lib/types';

// The rows of each source the timeline reads. The detail tabs page through the rest.
const AUDIT_ROWS = 100;

// The problems that are open now: states, not rows with a time, so they sit above the timeline.
function Problems({ list, prefix }: { list: Notification[]; prefix: string }) {
  if (!list.length) return null;
  return (
    <Card className="mb-4 border-bad/30">
      <ul className="divide-y divide-line">
        {list.map((n) => (
          <li key={n.id} className="flex min-h-11 items-center gap-3 px-4 py-2 text-sm">
            <Dot tone="bad" />
            <Badge>{moduleLabel(n.module)}</Badge>
            <span className="min-w-0 flex-1 truncate" title={n.message}>
              {n.subject}
              <span className="ml-2 text-muted">{n.message}</span>
            </span>
            {n.link ? (
              <Link to={`/${prefix}/${n.link}`} aria-label={`Open ${n.subject}`} className="text-muted transition-colors hover:text-fg">
                <ArrowUpRight className="size-4" />
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function TimelineItem({ row, prefix }: { row: TimelineRow; prefix: string }) {
  const open = row.href ? (
    <a href={row.href} target="_blank" rel="noreferrer" aria-label={`Open ${row.title}`} className="text-muted transition-colors hover:text-fg">
      <ArrowUpRight className="size-4" />
    </a>
  ) : row.link ? (
    <Link to={`/${prefix}/${row.link}`} aria-label={`Open ${row.title}`} className="text-muted transition-colors hover:text-fg">
      <ArrowUpRight className="size-4" />
    </Link>
  ) : null;
  return (
    <li className="cv-row flex items-start gap-3 border-b border-line px-4 py-3 last:border-0">
      <span className="mt-1.5">
        <Dot tone={row.tone} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <Badge>{moduleLabel(row.module)}</Badge>
          <span className={cx('truncate text-sm', row.kind === 'change' || row.kind === 'run' ? 'font-mono text-xs' : '')} title={row.title}>
            {row.title}
          </span>
        </div>
        {row.detail ? (
          <p className={cx('mt-1 truncate text-xs', row.tone === 'bad' ? 'text-bad' : 'text-muted')} title={row.detail}>
            {row.detail}
          </p>
        ) : null}
      </div>
      <span className="shrink-0 text-xs text-muted tabular-nums">{timeAgo(row.at)}</span>
      <span className="flex size-4 shrink-0 items-center">{open}</span>
    </li>
  );
}

// Events, errors, changes, runs, posts and CI runs of the org in one list, newest first, with the open problems above.
export function Timeline() {
  const { org, prefix } = useCurrentOrg();
  const [kind, setKind] = useState<TimelineKind | 'all'>('all');
  const [module, setModule] = useState('');
  const notes = useNotifications(prefix);
  const ci = useCi(prefix);
  const audit = useQuery({
    queryKey: ['audit', org?.id, 'timeline'],
    enabled: Boolean(org),
    queryFn: () => api<{ entries: AuditEntry[] }>(`/api/organizations/${org!.id}/audit?limit=${AUDIT_ROWS}`),
  });
  // The same requests as the Knowledge runs tab and the Alerts page, so they share the cache.
  const runs = useQuery({
    queryKey: ['knowledge', prefix, 'runs', false],
    queryFn: () => api<{ runs: KnowledgeRun[] }>(`/api/dashboard/${prefix}/knowledge/runs?limit=200`),
    enabled: Boolean(prefix),
    placeholderData: keepPreviousData,
  });
  const posts = useQuery({
    queryKey: ['webhooks', prefix, 'deliveries'],
    queryFn: () => api<DeliveryList>(`/api/dashboard/${prefix}/webhooks/deliveries?limit=20`),
    enabled: Boolean(prefix),
  });

  const rows = useMemo(
    () =>
      mergeTimeline(
        fromNotifications(notes.data?.notifications ?? []),
        fromAudit(audit.data?.entries ?? []),
        fromKnowledgeRuns(runs.data?.runs ?? []),
        fromDeliveries(posts.data?.deliveries ?? []),
        fromCi(ci.data?.repos ?? []),
      ),
    [notes.data, audit.data, runs.data, posts.data, ci.data],
  );
  const modules = useMemo(() => [...new Set(rows.map((r) => r.module))].sort(), [rows]);
  const shown = useMemo(() => rows.filter((r) => (kind === 'all' || r.kind === kind) && (!module || r.module === module)), [rows, kind, module]);
  const page = useShowMore(shown, `${kind}:${module}`, 50);
  const problems = (notes.data?.notifications ?? []).filter((n) => n.kind === 'problem' && !n.resolved_at);
  const loading = notes.isLoading || audit.isLoading;
  // A source that fails, such as knowledge runs with the module off, leaves its rows out. Only the main sources warn.
  const error = notes.error ?? audit.error;

  return (
    <>
      <Problems list={problems} prefix={prefix} />
      {error ? (
        <div className="mb-4">
          <ErrorNote error={error} />
        </div>
      ) : null}
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
          <Segmented
            label="Kind"
            value={kind}
            onChange={setKind}
            options={[{ value: 'all' as const, label: 'All' }, ...TIMELINE_KINDS]}
          />
          {modules.length > 1 ? (
            <Select value={module} onChange={(e) => setModule(e.target.value)} aria-label="Module" className="ml-auto h-8 w-40! text-xs">
              <option value="">All modules</option>
              {modules.map((m) => (
                <option key={m} value={m}>
                  {moduleLabel(m)}
                </option>
              ))}
            </Select>
          ) : null}
        </div>
        {loading ? (
          <SkeletonRows rows={8} />
        ) : page.shown.length ? (
          <>
            <ul>
              {page.shown.map((row) => (
                <TimelineItem key={row.id} row={row} prefix={prefix} />
              ))}
            </ul>
            <ShowMore list={page} noun="rows" />
          </>
        ) : (
          <EmptyState icon={History} title="Nothing here yet" />
        )}
      </Card>
    </>
  );
}
