import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Badge, cx, Dot, Table, Td, Th, Tr } from '../../components/ui';
import { type Tone, timeAgo } from '../../lib/format';
import type { KnowledgeSource } from '../../lib/types';
import { sourcePath } from './shared';

function sourceTone(s: KnowledgeSource): Tone {
  if (!s.crawl) return s.chunk_count ? 'ok' : 'muted';
  if (!s.crawl.enabled) return 'muted';
  if (s.crawl.last_error) return 'bad';
  return s.fetched_at ? 'ok' : 'warn';
}

function every(hours: number): string {
  return hours % 24 === 0 ? `every ${hours / 24}d` : `every ${hours}h`;
}

// The domain of a source is the first part of its key, before the first slash: asu/library-hours is in asu.
export function domainOf(key: string): string {
  const slash = key.indexOf('/');
  return slash > 0 ? key.slice(0, slash) : 'other';
}

export function countBy(values: string[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
}

// One pill for all domains and one for each domain, with its source count. An empty value is all domains.
export function DomainFilter({
  total,
  domains,
  value,
  onChange,
}: {
  total: number;
  domains: [string, number][];
  value: string;
  onChange: (domain: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Domains" className="mb-3 flex flex-wrap gap-1.5">
      {[['', total] as [string, number], ...domains].map(([d, n]) => (
        <button
          key={d || 'all'}
          type="button"
          role="tab"
          aria-selected={value === d}
          onClick={() => onChange(d)}
          className={cx(
            'flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs transition-colors',
            value === d ? 'border-fg bg-fg text-bg' : 'border-line text-muted hover:text-fg',
          )}
        >
          <span className={d ? 'font-mono' : undefined}>{d || 'All domains'}</span>
          <span className="tabular-nums opacity-70">{n}</span>
        </button>
      ))}
    </div>
  );
}

// The sources table. actions gives the row buttons; on a small screen they show under the source. The key and title
// open the full text of the source.
export function SourceTable({
  prefix,
  sources,
  actions,
}: {
  prefix: string;
  sources: KnowledgeSource[];
  actions: (s: KnowledgeSource, className?: string) => ReactNode;
}) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Source</Th>
          <Th className="hidden md:table-cell">Category</Th>
          <Th className="hidden text-right lg:table-cell">Passages</Th>
          <Th className="hidden lg:table-cell">Fetched</Th>
          <Th className="hidden sm:table-cell">Schedule</Th>
          <Th className="hidden sm:table-cell">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {sources.map((s) => (
          <Tr key={s.key}>
            <Td className="w-full max-w-0 py-2.5">
              <div className="flex items-start gap-2.5">
                <span className="mt-1.5">
                  <Dot tone={sourceTone(s)} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <Link
                      to={sourcePath(prefix, s.key)}
                      className="truncate rounded-sm font-mono text-xs font-medium underline-offset-2 hover:underline"
                      title={`Read ${s.key}`}
                    >
                      {s.key}
                    </Link>
                    {s.public ? <Badge tone="active">public</Badge> : null}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted" title={s.url ?? undefined}>
                    {s.title ? <span className="text-fg/80">{s.title}</span> : null}
                    {s.title && s.url ? ' · ' : null}
                    {s.url ?? (s.title ? null : 'no URL')}
                  </div>
                  {s.crawl?.last_error ? (
                    <div className="mt-0.5 line-clamp-2 text-xs text-bad" title={s.crawl.last_error}>
                      {s.crawl.last_error}
                    </div>
                  ) : null}
                  <div className="mt-0.5 text-xs text-muted sm:hidden">
                    {s.crawl ? (s.crawl.enabled ? every(s.crawl.fetch_every_hours) : 'paused') : s.url ? 'written by client' : 'document'} ·{' '}
                    {s.chunk_count} passages
                  </div>
                  {actions(s, 'mt-2 sm:hidden')}
                </div>
              </div>
            </Td>
            <Td className="hidden md:table-cell">
              <Badge>{s.category}</Badge>
            </Td>
            <Td className="hidden text-right text-xs text-muted tabular-nums lg:table-cell">{s.chunk_count}</Td>
            <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">
              <span title={s.crawl?.last_attempt_at ? `Last attempt ${timeAgo(s.crawl.last_attempt_at)}` : undefined}>
                {timeAgo(s.fetched_at)}
              </span>
            </Td>
            <Td className="hidden whitespace-nowrap sm:table-cell">
              {s.crawl ? (
                s.crawl.enabled ? (
                  <span className="text-xs text-muted">{every(s.crawl.fetch_every_hours)}</span>
                ) : (
                  <Badge>paused</Badge>
                )
              ) : (
                <Badge>{s.url ? 'written by client' : 'document'}</Badge>
              )}
            </Td>
            <Td className="hidden pl-0 sm:table-cell">{actions(s, 'justify-end')}</Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}
