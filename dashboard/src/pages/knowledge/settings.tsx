import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, CheckOption, Field, FormActions, Input, Select, SkeletonRows, Spinner } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { KnowledgeMode, KnowledgeSettings, KnowledgeTuning } from '../../lib/types';

// Limits from modules/knowledge/settings.py.
const LIMITS: Record<Exclude<keyof KnowledgeTuning, 'mode'>, [number, number]> = {
  chunk_chars: [100, 4000],
  chunk_overlap: [0, 2000],
  top_k: [1, 50],
  window: [0, 5],
  max_distance: [0.05, 2],
  rrf_k: [1, 200],
};

const MODES: { value: KnowledgeMode; label: string }[] = [
  { value: 'hybrid', label: 'Hybrid: vectors and text, fused' },
  { value: 'text', label: 'Text only: word match' },
  { value: 'vector', label: 'Vectors only: meaning match' },
];

type Draft = Record<keyof KnowledgeTuning, string>;

function toDraft(t: KnowledgeTuning): Draft {
  return Object.fromEntries(Object.entries(t).map(([k, v]) => [k, String(v)])) as Draft;
}

export function KnowledgeSettingsForm({ prefix, onDone }: { prefix: string; onDone: (message: string | null) => void }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['knowledge', prefix, 'settings'],
    queryFn: () => api<KnowledgeSettings>(`/api/dashboard/${prefix}/knowledge/settings`),
  });
  if (query.isLoading || !query.data) return <SkeletonRows />;
  return (
    <SettingsDraft
      prefix={prefix}
      data={query.data}
      onSaved={(next, reindex) => {
        client.setQueryData(['knowledge', prefix, 'settings'], next);
        onDone(reindex ? 'Saved. A job is crawling every crawled source again with the new passage size.' : 'Saved.');
      }}
      onCancel={() => onDone(null)}
    />
  );
}

function SettingsDraft({
  prefix,
  data,
  onSaved,
  onCancel,
}: {
  prefix: string;
  data: KnowledgeSettings;
  onSaved: (next: KnowledgeSettings, reindexed: boolean) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(toDraft(data.settings));
  const [reindex, setReindex] = useState(false);
  const number = (k: keyof typeof LIMITS) => Number(draft[k]);
  const valid = (k: keyof typeof LIMITS) => {
    const [lo, hi] = LIMITS[k];
    const n = number(k);
    return draft[k] !== '' && Number.isFinite(n) && n >= lo && n <= hi && (k === 'max_distance' || Number.isInteger(n));
  };
  const overlapOk = number('chunk_overlap') <= Math.floor(number('chunk_chars') / 2);
  const allOk = (Object.keys(LIMITS) as (keyof typeof LIMITS)[]).every(valid) && overlapOk;
  const chunking = draft.chunk_chars !== String(data.settings.chunk_chars) || draft.chunk_overlap !== String(data.settings.chunk_overlap);

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        mode: draft.mode,
        ...Object.fromEntries((Object.keys(LIMITS) as (keyof typeof LIMITS)[]).map((k) => [k, number(k)])),
      };
      const next = await send<KnowledgeSettings>(`/api/dashboard/${prefix}/knowledge/settings`, 'PUT', body);
      if (reindex) await send(`/api/dashboard/${prefix}/knowledge/reindex`, 'POST');
      return next;
    },
    onSuccess: (next) => onSaved(next, reindex),
  });

  const field = (k: keyof typeof LIMITS, label: string, hint: string, step = 1) => (
    <Field label={label} hint={valid(k) ? `${hint} Default ${data.defaults[k]}.` : `From ${LIMITS[k][0]} to ${LIMITS[k][1]}.`}>
      <Input
        type="number"
        min={LIMITS[k][0]}
        max={LIMITS[k][1]}
        step={step}
        value={draft[k]}
        onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
        aria-invalid={!valid(k)}
      />
    </Field>
  );

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (allOk) save.mutate();
      }}
    >
      <section className="space-y-4">
        <h3 className="text-sm font-medium">Index</h3>
        <div className="grid gap-5 sm:grid-cols-2">
          {field('chunk_chars', 'Passage size (characters)', 'Longer passages give more context per hit and fewer hits.', 50)}
          {field('chunk_overlap', 'Overlap (characters)', 'Text repeated from the end of the passage before.', 25)}
        </div>
        {!overlapOk ? <p className="text-xs text-bad">Overlap must be at most half the passage size.</p> : null}
        <p className="text-xs text-pretty text-muted">
          A new passage size applies the next time a source is indexed. Upload a document again to split it again.
        </p>
        {chunking ? (
          <CheckOption checked={reindex} onChange={setReindex} title="Crawl every crawled source again now">
            Pages are fetched one host at a time; a big pack takes a while.
          </CheckOption>
        ) : null}
      </section>

      <section className="space-y-4 border-t border-line pt-5">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">Search</h3>
          {data.embeddings.configured ? (
            <Badge tone="ok">embeddings: {data.embeddings.model}</Badge>
          ) : (
            <Badge tone="warn">no embedding service</Badge>
          )}
        </div>
        {!data.embeddings.configured ? (
          <p className="text-xs text-pretty text-muted">
            Without EMBEDDINGS_URL on the API, every mode searches on text only.
          </p>
        ) : null}
        <Field label="Mode" hint="Hybrid finds both exact words and paraphrases. Agents and the MCP server use the same mode.">
          <Select value={draft.mode} onChange={(e) => setDraft({ ...draft, mode: e.target.value })}>
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          {field('top_k', 'Results per search', 'Used when the caller sends no top_k.')}
          {field('window', 'Neighbor passages', 'Passages added on each side of a hit, for context.')}
          {field('max_distance', 'Vector distance limit', 'Cosine distance. Lower is stricter.', 0.05)}
          {field('rrf_k', 'Fusion constant (k)', 'Higher gives lower-ranked hits more weight.')}
        </div>
      </section>

      <FormActions error={save.error}>
        <Button variant="primary" disabled={!allOk || save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : reindex ? <RefreshCw className="size-4" /> : null}
          {reindex ? 'Save and reindex' : 'Save'}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setDraft(toDraft(data.defaults))}>
          <RotateCcw className="size-4" /> Defaults
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
