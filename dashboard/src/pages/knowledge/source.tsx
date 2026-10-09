import { useInfiniteQuery } from '@tanstack/react-query';
import { ArrowLeft, Check, Copy, ExternalLink, FileText } from 'lucide-react';
import { Fragment, type ReactNode, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  cx,
  EmptyState,
  ErrorNote,
  Mono,
  PageHeader,
  SkeletonRows,
  Spinner,
  Switch,
} from '../../components/ui';
import { api } from '../../lib/api';
import { compact, count, keyPath, timeAgo, when } from '../../lib/format';
import { useCurrentOrg } from '../../lib/org';
import type { KnowledgePassage, KnowledgeSourceText } from '../../lib/types';

// The lines of a passage as paragraphs. A line that starts with # is a heading.
function Paragraphs({ text }: { text: string }) {
  return text
    .split('\n')
    .filter((line) => line.trim())
    .map((line, i) => {
      const heading = /^(#{1,6})\s+(.*)$/.exec(line);
      return heading ? (
        <p key={i} className="mt-5 mb-2 font-semibold text-fg first:mt-0">
          {heading[2]}
        </p>
      ) : (
        <p key={i} className="mb-3 last:mb-0">
          {line}
        </p>
      );
    });
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-sm">{children}</dd>
    </div>
  );
}

// The full text of one knowledge source at /<org>/knowledge/sources/<key>. ?chunk= marks a search result passage.
export function KnowledgeSourcePage() {
  const { prefix } = useCurrentOrg();
  const key = useParams()['*'] ?? '';
  const [params] = useSearchParams();
  const chunk = params.get('chunk') ?? '';
  const [fromStart, setFromStart] = useState(false);
  const [rows, setRows] = useState(false);
  const [copied, setCopied] = useState(false);
  const focusRef = useRef<HTMLDivElement>(null);

  const text = useInfiniteQuery({
    queryKey: ['knowledge', prefix, 'source', key, chunk, fromStart],
    queryFn: ({ pageParam }) => {
      const query = new URLSearchParams();
      if (chunk) query.set('chunk', chunk);
      if (pageParam !== null) query.set('offset', String(pageParam));
      const suffix = query.size ? `?${query}` : '';
      return api<KnowledgeSourceText>(`/api/dashboard/${prefix}/knowledge/sources/${keyPath(key)}${suffix}`);
    },
    initialPageParam: fromStart ? 0 : (null as number | null),
    getNextPageParam: (last) => last.next_offset,
    enabled: Boolean(prefix && key),
  });

  const pages = text.data?.pages ?? [];
  const first = pages[0];
  const source = first?.source;
  const passages: KnowledgePassage[] = pages.flatMap((p) => p.passages);
  const focus = new Set(first?.focus ?? []);
  const shownFrom = first?.offset ?? 0;
  const firstFocus = passages.find((p) => focus.has(p.id))?.id;

  useEffect(() => {
    if (firstFocus) focusRef.current?.scrollIntoView({ block: 'nearest' });
  }, [firstFocus]);

  const copy = async () => {
    await navigator.clipboard.writeText(passages.map((p) => p.text).join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const back = (
    <Link
      to={`/${prefix}/knowledge`}
      className="mb-4 inline-flex items-center gap-1.5 rounded-sm text-sm text-muted transition-colors hover:text-fg"
    >
      <ArrowLeft className="size-4" /> Knowledge
    </Link>
  );

  if (text.error) {
    return (
      <>
        {back}
        <PageHeader title={key} />
        <ErrorNote error={text.error} />
      </>
    );
  }

  return (
    <>
      {back}
      <PageHeader
        title={source ? (source.title ?? source.key) : key}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Mono className="text-fg/80">{key}</Mono>
            {source ? <Badge>{source.category}</Badge> : null}
            {source?.public ? <Badge tone="active">public</Badge> : null}
            {source && !source.own ? <span className="text-xs">From another org</span> : null}
          </span>
        }
        action={
          source?.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-panel px-3 text-sm font-medium shadow-xs transition-colors hover:border-line-strong hover:bg-panel-2"
            >
              Open page <ExternalLink className="size-3.5" />
            </a>
          ) : null
        }
      />

      <Card className="mb-6">
        <dl className="grid grid-cols-2 gap-4 p-4 sm:grid-cols-3 lg:grid-cols-6">
          <Fact label="URL">
            {source?.url ? (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-muted hover:text-fg" title={source.url}>
                {source.url.replace(/^https?:\/\//, '')}
              </a>
            ) : source ? (
              <span className="text-muted">none</span>
            ) : (
              '-'
            )}
          </Fact>
          <Fact label="Fetched">
            <span title={source?.fetched_at ? when(source.fetched_at) : undefined}>{source ? timeAgo(source.fetched_at) : '-'}</span>
          </Fact>
          <Fact label="Updated">
            <span title={source?.updated_at ? when(source.updated_at) : undefined}>{source ? timeAgo(source.updated_at) : '-'}</span>
          </Fact>
          <Fact label="Passages">{source ? count(source.chunk_count) : '-'}</Fact>
          <Fact label="Characters">{source?.text_chars ? compact(source.text_chars) : '-'}</Fact>
          <Fact label="Embedding model">
            <span className="font-mono text-xs">{source?.embedding_model ?? 'none'}</span>
          </Fact>
        </dl>
      </Card>

      <Card>
        <CardHeader
          title="Text"
          hint={
            first
              ? first.total
                ? `Rows ${count(shownFrom + 1)} to ${count(shownFrom + passages.length)} of ${count(first.total)}. Repeated overlap is removed.`
                : undefined
              : undefined
          }
          action={
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs text-muted">
                <Switch checked={rows} onChange={setRows} label="Show passage rows" />
                <span className="hidden sm:inline">Rows</span>
              </label>
              <Button variant="ghost" onClick={copy} disabled={!passages.length} aria-label="Copy text">
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
              </Button>
            </div>
          }
        />
        {text.isLoading ? (
          <SkeletonRows rows={8} />
        ) : !passages.length ? (
          <EmptyState icon={FileText} title="No text yet">
            This source has no indexed text. A crawl or an upload adds it.
          </EmptyState>
        ) : (
          <>
            {shownFrom > 0 ? (
              <div className="border-b border-line bg-panel-2/40 px-4 py-2 text-xs text-muted">
                The text starts at the search match.{' '}
                <button type="button" className="font-medium text-fg underline-offset-2 hover:underline" onClick={() => setFromStart(true)}>
                  Show from the start
                </button>
              </div>
            ) : null}
            <article className="mx-auto max-w-3xl px-4 py-6 text-[15px] leading-7 text-fg/90 sm:px-8">
              {passages.map((p) => {
                const hit = focus.has(p.id);
                return (
                  <Fragment key={p.id}>
                    {rows ? (
                      <div className="mt-4 mb-2 flex items-center gap-2 text-[11px] text-muted first:mt-0">
                        <span className="font-mono">#{p.ordinal}</span>
                        <span className="h-px flex-1 bg-line" />
                      </div>
                    ) : null}
                    <div
                      ref={p.id === firstFocus ? focusRef : undefined}
                      data-focus={hit || undefined}
                      className={cx(
                        hit ? '-mx-3 my-3 rounded-md border-l-2 border-warn bg-warn/10 px-3 py-2' : 'mb-3',
                        rows && !hit && 'mb-0',
                      )}
                    >
                      {hit ? <div className="mb-1 text-[11px] font-medium tracking-wide text-warn uppercase">Search match</div> : null}
                      <Paragraphs text={p.text} />
                    </div>
                  </Fragment>
                );
              })}
            </article>
            {text.hasNextPage ? (
              <div className="flex justify-center border-t border-line p-3">
                <Button onClick={() => text.fetchNextPage()} disabled={text.isFetchingNextPage}>
                  {text.isFetchingNextPage ? <Spinner className="size-3.5" /> : null} Show more text
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Card>
    </>
  );
}
