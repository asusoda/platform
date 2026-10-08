import { useMutation } from '@tanstack/react-query';
import { Play } from 'lucide-react';
import { useState } from 'react';
import { Button, CheckOption, Field, FormActions, Input, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import { keyPath } from '../../lib/format';
import type { KnowledgeSource } from '../../lib/types';
import { useInvalidate } from './shared';

// Limits from modules/knowledge (KEY_PATTERN and crawl.MAX_EVERY_HOURS).
const KEY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/;
const MAX_EVERY_HOURS = 24 * 30;

// The full body PUT /knowledge/crawls/<key> takes, from a source.
export function crawlBody(s: KnowledgeSource, changes: { enabled?: boolean } = {}) {
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

type Draft = { key: string; url: string; category: string; title: string; every: string; public: boolean };

export function CrawlForm({
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
        <CheckOption checked={draft.public} onChange={(on) => setDraft({ ...draft, public: on })} title="Public">
          Every organization's agents can search a public source.
        </CheckOption>
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

export function RunCrawl({ prefix, source, onDone }: { prefix: string; source: KnowledgeSource; onDone: (queued: boolean) => void }) {
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
      <CheckOption checked={force} onChange={setForce} title="Force">
        Index the page again even if it did not change, and accept a page with much less text than last time.
      </CheckOption>
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
