import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { useState } from 'react';
import { Button, Code, Field, FormActions, Input, quietLink, Textarea } from '../../components/ui';
import { send } from '../../lib/api';
import { useSuperadmin } from '../../lib/queries';
import type { OrganizationDetail } from '../../lib/types';

const DESCRIPTION_MAX = 500;

// A whole number of zero or more, as typed.
const isCount = (value: string) => /^\d{1,9}$/.test(value);

export function GeneralForm({ org }: { org: OrganizationDetail }) {
  const client = useQueryClient();
  const superadmin = useSuperadmin();
  const saved = {
    description: org.description ?? '',
    perMessage: String(org.points_per_message ?? 1),
    cooldown: String(org.points_cooldown ?? 60),
  };
  const [draft, setDraft] = useState(saved);
  const changed = (Object.keys(saved) as (keyof typeof saved)[]).some((k) => draft[k] !== saved[k]);
  const valid = isCount(draft.perMessage) && isCount(draft.cooldown) && draft.description.length <= DESCRIPTION_MAX;
  const save = useMutation({
    mutationFn: () =>
      send(`/api/organizations/${org.id}/settings`, 'PUT', {
        description: draft.description.trim(),
        points_per_message: Number(draft.perMessage),
        points_cooldown: Number(draft.cooldown),
      }),
    onSuccess: () => {
      setDraft((d) => ({ ...d, description: d.description.trim() }));
      client.invalidateQueries({ queryKey: ['organization', org.id] });
      client.invalidateQueries({ queryKey: ['organizations'] });
      client.invalidateQueries({ queryKey: ['overview', org.prefix] });
    },
  });
  const set = (k: keyof typeof saved) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  return (
    <form
      className="space-y-5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Description" hint={`Shown where the org is listed. ${draft.description.length}/${DESCRIPTION_MAX}`}>
        <Textarea
          value={draft.description}
          onChange={set('description')}
          maxLength={DESCRIPTION_MAX}
          className="min-h-20"
          placeholder="What the org does"
        />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Points per message" hint="A whole number, 0 or more.">
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            value={draft.perMessage}
            onChange={set('perMessage')}
            aria-invalid={!isCount(draft.perMessage)}
            className="tabular-nums"
          />
        </Field>
        <Field label="Points cooldown (seconds)" hint="Time before the same member can earn message points again.">
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            value={draft.cooldown}
            onChange={set('cooldown')}
            aria-invalid={!isCount(draft.cooldown)}
            className="tabular-nums"
          />
        </Field>
      </div>
      <div className="rounded-lg border border-line bg-panel-2/40 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-medium">Officer role</div>
            <div className="mt-0.5 text-xs text-muted">
              Members with this Discord role can use this dashboard. Only the superadmin can change it.
            </div>
          </div>
          <div className="flex items-center gap-3">
            {org.officer_role_id ? <Code>{org.officer_role_id}</Code> : <span className="text-xs text-muted">Not set</span>}
            {superadmin.data ? (
              <Link to={`/${org.prefix}/admin`} className={quietLink}>
                Change
              </Link>
            ) : null}
          </div>
        </div>
      </div>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!changed || !valid || save.isPending}>
          Save general
        </Button>
        {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
      </FormActions>
    </form>
  );
}
