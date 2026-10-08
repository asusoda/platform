import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, ExternalLink, Pencil, Play, Plus, RefreshCw, Search, Trash2, X } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Code,
  cx,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  Select,
  SkeletonRows,
  Spinner,
  Stat,
  Switch,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { compact, keyPath, type Tone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { KnowledgeSource, SearchResponse } from '../lib/types';

// Limits from modules/knowledge (KEY_PATTERN and crawl.MAX_EVERY_HOURS).
const KEY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/;
const MAX_EVERY_HOURS = 24 * 30;
const WATCH_MS = 90_000;

function sourceTone(s: KnowledgeSource): Tone {
  if (!s.crawl) return s.chunk_count ? 'ok' : 'muted';
  if (!s.crawl.enabled) return 'muted';
  if (s.crawl.last_error) return 'bad';
  return s.fetched_at ? 'ok' : 'warn';
}

function every(hours: number): string {
  return hours % 24 === 0 ? `every ${hours / 24}d` : `every ${hours}h`;
}

// The full body PUT /knowledge/crawls/<key> takes, from a source.
function crawlBody(s: KnowledgeSource, changes: { enabled?: boolean } = {}) {
  return {
    url: s.url,
    category: s.category,
    title: s.title ?? undefined,
    fetch_every_hours: s.crawl?.fetch_every_hours ?? 24,
    public: s.public,
    enabled: s.crawl?.enabled ?? true,
    ...changes,
  };
}

// The domain of a source is the first part of its key, before the first slash: asu/library-hours is in asu.
function domainOf(key: string): string {
  const slash = key.indexOf('/');
  return slash > 0 ? key.slice(0, slash) : 'other';
}

function countBy(values: string[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
}

type Pack = { name: string; title: string; description: string; key_prefix: string; sources: number };

function SourcePacks({ prefix, onSynced }: { prefix: string; onSynced: (message: string) => void }) {
  const invalidate = useInvalidate(prefix);
  const packs = useQuery({
    queryKey: ['knowledge', prefix, 'packs'],
    queryFn: () => api<{ packs: Pack[] }>(`/api/dashboard/${prefix}/knowledge/packs`),
    enabled: Boolean(prefix),
  });
  const sync = useMutation({
    mutationFn: (pack: Pack) =>
      send<{ added: number; updated: number; retired: number }>(`/api/dashboard/${prefix}/knowledge/packs/${pack.name}/sync`, 'POST'),
    onSuccess: (r, pack) => {
      invalidate();
      onSynced(
        `${pack.title}: ${r.added} added, ${r.updated} updated, ${r.retired} retired. The crawl job fetches due pages in batches every 10 minutes.`,
      );
    },
  });
  if (!packs.data?.packs.length) return null;
  return (
    <Card className="mb-6">
      <CardHeader title="Source packs" hint="Ready-made sets of pages a module adds in one step. Sync again to pick up changes." />
      {packs.data.packs.map((pack) => (
        <div key={pack.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm font-medium">
              {pack.title}
              <Badge className="font-mono font-normal">{pack.key_prefix}</Badge>
            </div>
            <div className="mt-0.5 text-xs text-pretty text-muted">{pack.description}</div>
          </div>
          <span className="text-xs text-muted tabular-nums">{pack.sources ? `${pack.sources} sources` : 'not added'}</span>
          <Button onClick={() => sync.mutate(pack)} disabled={sync.isPending}>
            {sync.isPending && sync.variables?.name === pack.name ? <Spinner /> : <RefreshCw className="size-4" />}
            {pack.sources ? 'Sync' : 'Add'}
          </Button>
        </div>
      ))}
      {sync.error ? (
        <div className="p-4 pt-0">
          <ErrorNote error={sync.error} />
        </div>
      ) : null}
    </Card>
  );
}

function useInvalidate(prefix: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: ['knowledge', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
  };
}

// Forms

type Draft = { key: string; url: string; category: string; title: string; every: string; public: boolean };

function CrawlForm({
  prefix,
  source,
  categories,
  canPublish,
  onDone,
}: {
  prefix: string;
  source: KnowledgeSource | null;
  categories: string[];
  canPublish: boolean;
  onDone: () => void;
}) {
  const invalidate = useInvalidate(prefix);
  const [draft, setDraft] = useState<Draft>({
    key: source?.key ?? '',
    url: source?.url ?? '',
    category: source?.category ?? '',
    title: source?.title ?? '',
    every: String(source?.crawl?.fetch_every_hours ?? 24),
    public: source?.public ?? false,
  });
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const hours = Number(draft.every);
  const keyOk = !draft.key || KEY_PATTERN.test(draft.key);
  const urlOk = !draft.url || /^https?:\/\/\S+$/.test(draft.url);
  const hoursOk = Number.isInteger(hours) && hours >= 1 && hours <= MAX_EVERY_HOURS;
  const ready = KEY_PATTERN.test(draft.key) && /^https?:\/\/\S+$/.test(draft.url) && draft.category.trim() && hoursOk;
  const save = useMutation({
    mutationFn: () =>
      send<KnowledgeSource>(`/api/dashboard/${prefix}/knowledge/crawls/${keyPath(draft.key)}`, 'PUT', {
        url: draft.url,
        category: draft.category.trim(),
        title: draft.title.trim() || undefined,
        fetch_every_hours: hours,
        public: draft.public,
        enabled: source?.crawl?.enabled ?? true,
      }),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          label="Key"
          hint={
            source
              ? 'The key names the source and cannot change.'
              : keyOk
                ? 'Letters, digits and . _ : / -, for example club/faq.'
                : 'Start with a letter or digit; use only letters, digits and . _ : / -'
          }
        >
          <Input
            value={draft.key}
            onChange={set('key')}
            placeholder="club/faq"
            className="font-mono"
            readOnly={Boolean(source)}
            aria-invalid={!keyOk}
            required
            autoFocus={!source}
          />
        </Field>
        <Field label="Category" hint="Agents can search one category at a time.">
          <Input value={draft.category} onChange={set('category')} placeholder="club" list="knowledge-categories" required />
        </Field>
        <div className="sm:col-span-2">
          <Field label="URL" hint={urlOk ? 'A public page. The crawler reads its main text.' : 'Must start with http:// or https://'}>
            <Input
              type="url"
              value={draft.url}
              onChange={(e) => setDraft({ ...draft, url: e.target.value.trim() })}
              placeholder="https://example.org/faq"
              aria-invalid={!urlOk}
              required
              autoFocus={Boolean(source)}
            />
          </Field>
        </div>
        <Field label="Title (optional)" hint="Empty keeps the title read from the page.">
          <Input value={draft.title} onChange={set('title')} placeholder="Club FAQ" />
        </Field>
        <Field
          label="Fetch every (hours)"
          hint={hoursOk ? `From 1 to ${MAX_EVERY_HOURS} (30 days).` : `Must be a whole number from 1 to ${MAX_EVERY_HOURS}.`}
        >
          <Input type="number" min={1} max={MAX_EVERY_HOURS} step={1} value={draft.every} onChange={set('every')} aria-invalid={!hoursOk} />
        </Field>
      </div>
      <datalist id="knowledge-categories">
        {categories.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {canPublish || draft.public ? (
        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line p-3 text-sm transition-colors hover:bg-panel-2/50 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-current"
            checked={draft.public}
            onChange={(e) => setDraft({ ...draft, public: e.target.checked })}
          />
          <span className="min-w-0">
            <span className="block font-medium">Public</span>
            <span className="mt-0.5 block text-xs text-muted">
              Every organization's agents can search a public source.
            </span>
          </span>
        </label>
      ) : null}
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!ready || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : null}
          {source ? 'Save crawl' : 'Add crawl'}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function RunCrawl({ prefix, source, onDone }: { prefix: string; source: KnowledgeSource; onDone: (queued: boolean) => void }) {
  const [force, setForce] = useState(false);
  const run = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/knowledge/crawls/${keyPath(source.key)}/run`, 'POST', { force }),
    onSuccess: () => onDone(true),
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        run.mutate();
      }}
    >
      <p className="text-sm text-pretty text-muted">
        Fetches <span className="break-all text-fg">{source.url}</span> now. The result shows on the source when the job ends.
      </p>
      <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line p-3 text-sm transition-colors hover:bg-panel-2/50 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring">
        <input type="checkbox" className="mt-0.5 size-4 accent-current" checked={force} onChange={(e) => setForce(e.target.checked)} />
        <span className="min-w-0">
          <span className="block font-medium">Force</span>
          <span className="mt-0.5 block text-xs text-muted">
            Index the page again even if it did not change, and accept a page with much less text than last time.
          </span>
        </span>
      </label>
      <FormActions error={run.error}>
        <Button variant="primary" disabled={run.isPending}>
          {run.isPending ? <Spinner className="size-3.5" /> : <Play className="size-4" />}
          Run now
        </Button>
        <Button type="button" variant="ghost" onClick={() => onDone(false)}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

// Search

function TestSearch({ prefix, categories }: { prefix: string; categories: string[] }) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const search = useMutation({
    mutationFn: () =>
      send<SearchResponse>(`/api/dashboard/${prefix}/knowledge/search`, 'POST', {
        query: query.trim(),
        category: category || undefined,
        top_k: 8,
      }),
  });
  return (
    <Card className="mt-6">
      <CardHeader title="Test search" hint="The passages an agent of this org gets for a query, from its sources and public ones." />
      <form
        className="grid gap-2 border-b border-line p-4 sm:grid-cols-[minmax(0,1fr)_11rem_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) search.mutate();
        }}
      >
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="When is the next build night?"
          aria-label="Search query"
        />
        <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
        <Button variant="primary" disabled={!query.trim() || search.isPending} className="h-9">
          {search.isPending ? <Spinner className="size-3.5" /> : <Search className="size-4" />}
          Search
        </Button>
      </form>
      {search.error ? (
        <div className="p-4">
          <ErrorNote error={search.error} />
        </div>
      ) : search.data ? (
        search.data.results.length ? (
          <>
            {!search.data.dense ? (
              <p className="border-b border-line bg-panel-2/40 px-4 py-2 text-xs text-muted">
                Text match only: no embedding service answered, so results did not use vectors.
              </p>
            ) : null}
            <ol>
              {search.data.results.map((r, i) => (
                <li key={r.chunk_id} className="border-b border-line px-4 py-3 last:border-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="w-5 text-xs text-muted tabular-nums">{i + 1}.</span>
                    <Code>{r.source_key}</Code>
                    {r.title ? <span className="min-w-0 truncate text-sm font-medium">{r.title}</span> : null}
                    <Badge>{r.category}</Badge>
                    {r.public ? <Badge tone="active">public</Badge> : null}
                    <Mono className="ml-auto tabular-nums" title="Reciprocal rank fusion score">
                      {r.score.toFixed(4)}
                    </Mono>
                  </div>
                  <p className="mt-1.5 line-clamp-4 pl-7 text-sm whitespace-pre-line text-pretty text-muted">{r.content}</p>
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 ml-7 inline-flex max-w-[calc(100%-1.75rem)] items-center gap-1 text-xs text-muted hover:text-fg"
                    >
                      <span className="truncate">{r.url}</span>
                      <ExternalLink className="size-3 shrink-0" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <EmptyState icon={Search} title="No passages match">
            Try other words, or all categories.
          </EmptyState>
        )
      ) : null}
    </Card>
  );
}

// Page

export function KnowledgePage() {
  const { prefix } = useCurrentOrg();
  const invalidate = useInvalidate(prefix);
  const [editing, setEditing] = useState<KnowledgeSource | 'new' | null>(null);
  const [running, setRunning] = useState<KnowledgeSource | null>(null);
  const [filter, setFilter] = useState('');
  const [domain, setDomain] = useState('');
  const [watchUntil, setWatchUntil] = useState(0);
  const [notice, setNotice] = useState<ReactNode>(null);
  const list = useQuery({
    queryKey: ['knowledge', prefix, 'sources'],
    queryFn: () => api<{ sources: KnowledgeSource[]; can_publish: boolean }>(`/api/dashboard/${prefix}/knowledge/sources`),
    enabled: Boolean(prefix),
    refetchInterval: () => (Date.now() < watchUntil ? 5_000 : false),
  });
  const toggle = useMutation({
    mutationFn: (s: KnowledgeSource) =>
      send(`/api/dashboard/${prefix}/knowledge/crawls/${keyPath(s.key)}`, 'PUT', crawlBody(s, { enabled: !s.crawl?.enabled })),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (key: string) => send(`/api/dashboard/${prefix}/knowledge/sources/${keyPath(key)}`, 'DELETE'),
    onSuccess: invalidate,
  });

  const sources = list.data?.sources ?? [];
  const categories = [...new Set(sources.map((s) => s.category))].sort();
  const domains = countBy(sources.map((s) => domainOf(s.key)));
  const shown = sources.filter((s) => (!filter || s.category === filter) && (!domain || domainOf(s.key) === domain));
  const crawled = sources.filter((s) => s.crawl);
  const failing = crawled.filter((s) => s.crawl?.last_error);
  const chunks = sources.reduce((n, s) => n + s.chunk_count, 0);
  const actionError = toggle.error ?? remove.error;
  // Row actions: crawled sources get schedule, run and edit controls; every source can be deleted.
  const actions = (s: KnowledgeSource, className?: string) => (
    <div className={cx('flex items-center gap-1', className)}>
      {s.crawl ? (
        <>
          <Switch
            checked={s.crawl.enabled}
            onChange={() => toggle.mutate(s)}
            disabled={toggle.isPending && toggle.variables?.key === s.key}
            label={`Crawl ${s.key} on schedule`}
          />
          <Button variant="ghost" size="icon" title="Run now" aria-label={`Run crawl of ${s.key} now`} onClick={() => setRunning(s)}>
            <Play className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${s.key}`} onClick={() => setEditing(s)}>
            <Pencil className="size-4" />
          </Button>
        </>
      ) : null}
      <Button
        variant="ghost"
        size="icon"
        title="Delete"
        aria-label={`Delete ${s.key}`}
        className={cx('hover:text-bad', remove.isPending && remove.variables === s.key && 'opacity-50')}
        onClick={() => {
          if (confirm(`Delete ${s.key} and its ${s.chunk_count} passages? Agents stop finding it at once.`)) {
            remove.mutate(s.key);
          }
        }}
      >
        <Trash2 className="size-4" />
      </Button>
    </div>
  );

  const addCrawl = (
    <Button variant="primary" onClick={() => setEditing('new')}>
      <Plus className="size-4" /> Add crawl
    </Button>
  );

  return (
    <>
      <PageHeader
        title="Knowledge"
        description="The sources agents search, by domain: source packs, pages the platform crawls on a schedule, and documents that clients write."
        action={addCrawl}
      />
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Sources" value={list.data ? sources.length : '-'} />
        <Stat label="Crawled on a schedule" value={list.data ? crawled.length : '-'} />
        <Stat
          label="Failing crawls"
          value={<span className={failing.length ? 'text-bad' : undefined}>{list.data ? failing.length : '-'}</span>}
        />
        <Stat label="Indexed passages" value={list.data ? compact(chunks) : '-'} />
      </div>
      {notice ? (
        <div role="status" className="mb-4 flex items-start gap-3 rounded-md border border-line bg-panel-2 px-3 py-2 text-sm">
          <div className="min-w-0 flex-1 text-pretty">{notice}</div>
          <button type="button" aria-label="Dismiss" className="text-muted hover:text-fg" onClick={() => setNotice(null)}>
            <X className="size-4" />
          </button>
        </div>
      ) : null}
      {list.error || actionError ? (
        <div className="mb-4">
          <ErrorNote error={list.error ?? actionError} />
        </div>
      ) : null}
      <SourcePacks
        prefix={prefix}
        onSynced={(message) => {
          setWatchUntil(Date.now() + WATCH_MS);
          setNotice(message);
        }}
      />
      {domains.length > 1 ? (
        <div role="tablist" aria-label="Domains" className="mb-3 flex flex-wrap gap-1.5">
          {[['', sources.length] as [string, number], ...domains].map(([d, n]) => (
            <button
              key={d || 'all'}
              type="button"
              role="tab"
              aria-selected={domain === d}
              onClick={() => setDomain(d)}
              className={cx(
                'flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs transition-colors',
                domain === d ? 'border-fg bg-fg text-bg' : 'border-line text-muted hover:text-fg',
              )}
            >
              <span className={d ? 'font-mono' : undefined}>{d || 'All domains'}</span>
              <span className="tabular-nums opacity-70">{n}</span>
            </button>
          ))}
        </div>
      ) : null}
      <Card>
        <CardHeader
          title="Sources"
          hint={list.data ? `${shown.length} of ${sources.length} sources` : undefined}
          action={
            categories.length > 1 ? (
              <Select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by category" className="h-8 w-auto text-xs">
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            ) : null
          }
        />
        {list.isLoading ? (
          <SkeletonRows />
        ) : shown.length ? (
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
              {shown.map((s) => (
                <Tr key={s.key}>
                  <Td className="w-full max-w-0 py-2.5">
                    <div className="flex items-start gap-2.5">
                      <span className="mt-1.5">
                        <Dot tone={sourceTone(s)} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-mono text-xs font-medium" title={s.key}>
                            {s.key}
                          </span>
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
                          {s.crawl ? (s.crawl.enabled ? every(s.crawl.fetch_every_hours) : 'paused') : 'written by client'} ·{' '}
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
                      <Badge>written by client</Badge>
                    )}
                  </Td>
                  <Td className="hidden pl-0 sm:table-cell">
                    {actions(s, 'justify-end')}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={Database} title="No sources yet" action={addCrawl}>
            Add a source pack above, add a page to crawl on a schedule, or write documents with a knowledge:write token.
          </EmptyState>
        )}
      </Card>

      <TestSearch prefix={prefix} categories={categories} />

      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing && editing !== 'new' ? `Edit ${editing.key}` : 'Add crawl'}
        description="A crawl fetches a page on a schedule, splits its text into passages and indexes them for agents."
        wide
      >
        {editing ? (
          <CrawlForm
            prefix={prefix}
            source={editing === 'new' ? null : editing}
            categories={categories}
            canPublish={list.data?.can_publish ?? false}
            onDone={() => setEditing(null)}
          />
        ) : null}
      </Dialog>

      <Dialog open={running !== null} onClose={() => setRunning(null)} title={running ? `Run ${running.key}` : 'Run crawl'}>
        {running ? (
          <RunCrawl
            prefix={prefix}
            source={running}
            onDone={(queued) => {
              if (queued) {
                setNotice(
                  <>
                    Queued a crawl of <Mono className="text-fg">{running.key}</Mono>. The row updates when it ends.
                  </>,
                );
                setWatchUntil(Date.now() + WATCH_MS);
                invalidate();
              }
              setRunning(null);
            }}
          />
        ) : null}
      </Dialog>
    </>
  );
}
