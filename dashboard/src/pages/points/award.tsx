import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Dialog, Field, FormActions, Input } from '../../components/ui';
import { send } from '../../lib/api';
import type { PointsMember } from '../../lib/types';

// A Discord user ID: the add_points route finds members by it.
const DISCORD_ID = /^[0-9]{15,25}$/;

export function AwardDialog({
  prefix,
  members,
  open,
  onClose,
}: {
  prefix: string;
  members: PointsMember[];
  open: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState({ member: '', points: '', event: '', by: '' });
  const award = useMutation({
    mutationFn: () => {
      const body = { points: Number(draft.points), event: draft.event || null, awarded_by_officer: draft.by || null };
      return DISCORD_ID.test(draft.member)
        ? send(`/api/points/${prefix}/add_points`, 'POST', { ...body, user_discord_id: draft.member })
        : send(`/api/points/${prefix}/assign_points`, 'POST', { ...body, user_identifier: draft.member });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['points', prefix] });
      setDraft({ member: '', points: '', event: '', by: '' });
      onClose();
    },
  });
  const set = (k: keyof typeof draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const points = Number(draft.points);
  return (
    <Dialog open={open} onClose={onClose} title="Award points" description="Add points to one member. Use a negative number to take points away.">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          award.mutate();
        }}
      >
        <Field label="Member" hint="Email, username or Discord user ID.">
          <Input value={draft.member} onChange={set('member')} list="points-members" placeholder="ada@example.edu" required autoFocus />
        </Field>
        <datalist id="points-members">
          {members.map((m) => (m.email ? <option key={m.id} value={m.email}>{m.name}</option> : null))}
        </datalist>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Points">
            <Input type="number" step="any" value={draft.points} onChange={set('points')} placeholder="10" required />
          </Field>
          <Field label="Event" hint="Optional. Groups the entry on the Events tab.">
            <Input value={draft.event} onChange={set('event')} placeholder="Build night" />
          </Field>
        </div>
        <Field label="Awarded by" hint="Optional. Empty records your name.">
          <Input value={draft.by} onChange={set('by')} />
        </Field>
        <FormActions error={award.error}>
          <Button variant="primary" disabled={!draft.member || !points || award.isPending}>
            Award points
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}
