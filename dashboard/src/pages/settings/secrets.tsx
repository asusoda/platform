import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Badge, Button, ErrorNote, Input } from '../../components/ui';
import { send } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import type { SecretState } from '../../lib/types';

export function SecretRow({ orgId, secret }: { orgId: number; secret: SecretState & { updated_at?: string | null } }) {
  const client = useQueryClient();
  const [value, setValue] = useState('');
  const refresh = () => client.invalidateQueries({ queryKey: ['secrets', orgId] });
  const save = useMutation({
    mutationFn: () => send(`/api/organizations/${orgId}/secrets/${secret.name}`, 'PUT', { value }),
    onSuccess: () => {
      setValue('');
      refresh();
    },
  });
  const clear = useMutation({ mutationFn: () => send(`/api/organizations/${orgId}/secrets/${secret.name}`, 'DELETE'), onSuccess: refresh });
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0">
      <div className="min-w-0 flex-1 basis-56">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          {secret.name}
          <Badge tone={secret.set ? 'ok' : 'muted'}>{secret.set ? `set ${timeAgo(secret.updated_at)}` : 'not set'}</Badge>
        </div>
        <div className="mt-1 text-xs text-muted">{secret.description}</div>
      </div>
      <form
        className="flex w-full gap-2 sm:w-auto"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder="New value" className="min-w-0 sm:w-48" aria-label={`New value for ${secret.name}`} />
        <Button disabled={!value || save.isPending}>Save</Button>
        {secret.set ? (
          <Button type="button" variant="danger" onClick={() => clear.mutate()}>
            Remove
          </Button>
        ) : null}
      </form>
      {save.error ? (
        <div className="w-full">
          <ErrorNote error={save.error} />
        </div>
      ) : null}
    </div>
  );
}
