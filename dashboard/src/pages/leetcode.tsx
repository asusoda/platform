import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Badge, Button, Card, CardHeader, ErrorNote, Field, FormActions, Input, PageHeader, SkeletonRows } from '../components/ui';
import { api, send } from '../lib/api';
import { useCurrentOrg } from '../lib/org';
import type { LeetCodeSettings } from '../lib/types';

// The checks save_settings makes on the server.
const isSnowflake = (value: string) => !value || /^[0-9]{5,25}$/.test(value);
const isTime = (value: string) => !value || /^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(value);

function LeetCodeForm({ orgId, saved }: { orgId: number; saved: LeetCodeSettings }) {
  const client = useQueryClient();
  const initial = { channel: saved.channel_id ?? '', role: saved.role_ping ?? '', time: saved.daily_time ?? '' };
  const [draft, setDraft] = useState(initial);
  const changed = draft.channel !== initial.channel || draft.role !== initial.role || draft.time !== initial.time;
  const valid = isSnowflake(draft.channel) && isSnowflake(draft.role) && isTime(draft.time);
  const save = useMutation({
    mutationFn: () =>
      send<{ settings: LeetCodeSettings }>(`/api/organizations/${orgId}/leetcode`, 'PUT', {
        channel_id: draft.channel || null,
        role_ping: draft.role || null,
        daily_time: draft.time || null,
      }),
    onSuccess: (body) => client.setQueryData(['leetcode-settings', orgId], (old: object | undefined) => ({ ...old, ...body })),
  });
  const set = (k: keyof typeof initial) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value.trim() });
  return (
    <form
      className="space-y-5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Channel ID" hint={isSnowflake(draft.channel) ? 'Empty turns the post off.' : 'Must be a Discord ID (digits only).'}>
          <Input
            value={draft.channel}
            onChange={set('channel')}
            inputMode="numeric"
            placeholder="1290000000000000000"
            className="font-mono"
            aria-invalid={!isSnowflake(draft.channel)}
          />
        </Field>
        <Field label="Role to ping" hint={isSnowflake(draft.role) ? 'Optional.' : 'Must be a Discord ID (digits only).'}>
          <Input
            value={draft.role}
            onChange={set('role')}
            inputMode="numeric"
            placeholder="1290000000000000000"
            className="font-mono"
            aria-invalid={!isSnowflake(draft.role)}
          />
        </Field>
        <Field label="Daily time" hint="Server time. Empty means 09:00.">
          <Input type="time" value={draft.time} onChange={set('time')} aria-invalid={!isTime(draft.time)} className="tabular-nums" />
        </Field>
      </div>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!changed || !valid || save.isPending}>
          Save LeetCode
        </Button>
        {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
      </FormActions>
    </form>
  );
}

export function LeetCodePage() {
  const { org } = useCurrentOrg();
  const leetcode = useQuery({
    queryKey: ['leetcode-settings', org?.id],
    queryFn: () => api<{ settings: LeetCodeSettings; enabled: boolean }>(`/api/organizations/${org?.id}/leetcode`),
    enabled: org !== undefined,
  });
  const settings = leetcode.data?.settings;
  return (
    <>
      <PageHeader />
      <div className="space-y-6">
        <Card>
          <CardHeader
            title="Daily post"
            action={
              settings ? (
                <Badge tone={settings.channel_id ? 'ok' : 'muted'}>
                  {settings.channel_id ? `Daily at ${settings.daily_time ?? '09:00'}` : 'Off'}
                </Badge>
              ) : null
            }
          />
          {leetcode.data && org ? (
            <LeetCodeForm key={org.id} orgId={org.id} saved={leetcode.data.settings} />
          ) : leetcode.error ? (
            <div className="p-4">
              <ErrorNote error={leetcode.error} />
            </div>
          ) : (
            <SkeletonRows rows={3} />
          )}
        </Card>
      </div>
    </>
  );
}
