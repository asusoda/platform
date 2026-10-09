import { useMutation } from '@tanstack/react-query';
import { ExternalLink, FileText, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Badge, Button, Card, CardHeader, Code, EmptyState, ErrorNote, Input, Mono, Select, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import type { SearchResponse } from '../../lib/types';
import { sourcePath } from './shared';

export function TestSearch({ prefix, categories }: { prefix: string; categories: string[] }) {
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
                    <Link
                      to={sourcePath(prefix, r.source_key, r.chunk_id)}
                      className="flex min-w-0 items-center gap-2"
                      title={`Read ${r.source_key}`}
                    >
                      <Code className="hover:border-line-strong">{r.source_key}</Code>
                      {r.title ? <span className="min-w-0 truncate text-sm font-medium hover:underline">{r.title}</span> : null}
                    </Link>
                    <Badge>{r.category}</Badge>
                    {r.public ? <Badge tone="active">public</Badge> : null}
                    <Mono className="ml-auto tabular-nums" title="Reciprocal rank fusion score">
                      {r.score.toFixed(4)}
                    </Mono>
                  </div>
                  <p className="mt-1.5 line-clamp-4 pl-7 text-sm whitespace-pre-line text-pretty text-muted">{r.content}</p>
                  <div className="mt-1 flex min-w-0 items-center gap-3 pl-7 text-xs text-muted">
                    <Link
                      to={sourcePath(prefix, r.source_key, r.chunk_id)}
                      className="inline-flex shrink-0 items-center gap-1 hover:text-fg"
                    >
                      <FileText className="size-3" /> Full text
                    </Link>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-1 hover:text-fg">
                        <span className="truncate">{r.url}</span>
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : null}
                  </div>
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
