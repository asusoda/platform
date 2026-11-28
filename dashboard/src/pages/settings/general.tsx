import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { useState } from 'react';
import { Button, Code, Field, FormActions, quietLink, Textarea } from '../../components/ui';
import { send } from '../../lib/api';
import { useSuperadmin } from '../../lib/queries';
import type { OrganizationDetail } from '../../lib/types';

const DESCRIPTION_MAX = 500;

export function GeneralForm({ org }: { org: OrganizationDetail }) {
  const client = useQueryClient();
  const superadmin = useSuperadmin();
  const saved = org.description ?? '';
  const [draft, setDraft] = useState(saved);
  const changed = draft !== saved;
  const valid = draft.length <= DESCRIPTION_MAX;
  const save = useMutation({
    mutationFn: () => send(`/api/organizations/${org.id}/settings`, 'PUT', { description: draft.trim() }),
    onSuccess: () => {
      setDraft((d) => d.trim());
      client.invalidateQueries({ queryKey: ['organization', org.id] });
      client.invalidateQueries({ queryKey: ['organizations'] });
      client.invalidateQueries({ queryKey: ['overview', org.prefix] });
    },
  });
  return (
    <form
      className="space-y-5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Description" hint={`Shown where the org is listed. ${draft.length}/${DESCRIPTION_MAX}`}>
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={DESCRIPTION_MAX}
          className="min-h-20"
          placeholder="What the org does"
        />
      </Field>
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
