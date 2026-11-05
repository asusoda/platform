import { useMutation } from '@tanstack/react-query';
import { Check, X } from 'lucide-react';
import { Button, Card, CardHeader, ErrorNote } from '../../components/ui';
import { send } from '../../lib/api';
import { keyPath } from '../../lib/format';
import type { KnowledgeSource } from '../../lib/types';

// Pages an agent read on a site outside the automatic list. Approve starts their crawl; Reject keeps them off.
export function ReviewCard({
  prefix,
  pending,
  onChange,
}: {
  prefix: string;
  pending: KnowledgeSource[];
  onChange: () => void;
}) {
  const decide = useMutation({
    mutationFn: ({ key, approve }: { key: string; approve: boolean }) =>
      send(`/api/dashboard/${prefix}/knowledge/sources/${keyPath(key)}/review`, 'POST', { approve }),
    onSuccess: onChange,
  });
  if (!pending.length) return null;
  return (
    <Card className="mb-6">
      <CardHeader title="Pages to review" hint={`${pending.length} read by agents`} />
      {decide.error ? (
        <div className="px-4 pt-3">
          <ErrorNote error={decide.error} />
        </div>
      ) : null}
      <ul className="divide-y divide-line">
        {pending.map((s) => {
          const busy = decide.isPending && decide.variables?.key === s.key;
          return (
            <li key={s.key} className="flex items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <a
                  href={s.url ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className="block truncate text-sm underline-offset-2 hover:underline"
                  title={s.url ?? undefined}
                >
                  {s.url}
                </a>
                <div className="truncate text-xs text-muted">{s.category}</div>
              </div>
              <Button disabled={busy} onClick={() => decide.mutate({ key: s.key, approve: true })}>
                <Check className="size-4" /> Approve
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => decide.mutate({ key: s.key, approve: false })}
              >
                <X className="size-4" /> Reject
              </Button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
