import type { AuditEntry } from '../lib/types';
import { timeAgo } from '../lib/format';
import { History } from 'lucide-react';
import { Dot, EmptyState } from './ui';

function tone(entry: AuditEntry) {
  const result = entry.details?.result;
  if (result === 'failed' || (entry.status ?? 0) >= 400) return 'bad' as const;
  return 'ok' as const;
}

export function ActivityList({ entries, empty, showOrg = false }: { entries: AuditEntry[]; empty: string; showOrg?: boolean }) {
  if (!entries.length) return <EmptyState icon={History}>{empty}</EmptyState>;
  return (
    <ul>
      {entries.map((e) => (
        <li key={e.id} className="cv-row flex items-start gap-3 border-b border-line px-4 py-3 last:border-0">
          <span className="mt-1.5">
            <Dot tone={tone(e)} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate font-mono text-xs">{e.action}</div>
            <div className="mt-0.5 truncate text-xs text-muted">
              {showOrg ? `${e.org ?? 'no org'} · ` : ''}
              {e.actor_kind === 'job'
                ? String(e.details?.result ?? 'ran')
                : e.actor_kind
                  ? `${e.actor_kind}${e.actor_id ? ` ${e.actor_id}` : ''}`
                  : e.source}
              {e.status ? ` · ${e.status}` : ''}
            </div>
          </div>
          <span className="shrink-0 text-xs text-muted tabular-nums">{timeAgo(e.created_at)}</span>
        </li>
      ))}
    </ul>
  );
}
