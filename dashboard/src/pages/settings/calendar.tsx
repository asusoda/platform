import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Info } from 'lucide-react';
import { useState } from 'react';
import { Button, Field, FormActions, Input, Switch } from '../../components/ui';
import { send } from '../../lib/api';
import type { CalendarSettings } from '../../lib/types';

export function CalendarForm({ orgId, saved }: { orgId: number; saved: CalendarSettings }) {
  const client = useQueryClient();
  const initial = {
    notion: saved.notion_database_id ?? '',
    google: saved.google_calendar_id ?? '',
    sync: saved.calendar_sync_enabled,
  };
  const [draft, setDraft] = useState(initial);
  const changed = draft.notion !== initial.notion || draft.google !== initial.google || draft.sync !== initial.sync;
  const save = useMutation({
    mutationFn: () =>
      send(`/api/organizations/${orgId}/calendar`, 'PUT', {
        notion_database_id: draft.notion || null,
        google_calendar_id: draft.google || null,
        calendar_sync_enabled: draft.sync,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['calendar-settings', orgId] }),
  });
  return (
    <form
      className="space-y-5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Notion database ID" hint="The events database the sync reads.">
          <Input
            value={draft.notion}
            onChange={(e) => setDraft({ ...draft, notion: e.target.value.trim() })}
            placeholder="1a2b3c4d5e6f..."
            className="font-mono"
            spellCheck={false}
          />
        </Field>
        <Field label="Google calendar ID" hint="The calendar the sync writes to.">
          <Input
            value={draft.google}
            onChange={(e) => setDraft({ ...draft, google: e.target.value.trim() })}
            placeholder="abc123@group.calendar.google.com"
            className="font-mono"
            spellCheck={false}
          />
        </Field>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-line p-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">Sync Notion to Google Calendar</div>
          <div className="mt-0.5 text-xs text-muted">Runs on the server's calendar sync schedule.</div>
        </div>
        <Switch checked={draft.sync} onChange={(sync) => setDraft({ ...draft, sync })} label="Sync Notion to Google Calendar" />
      </div>
      <p className="flex items-start gap-2 rounded-lg border border-line bg-panel-2/40 p-3 text-xs text-pretty text-muted">
        <Info className="mt-px size-3.5 shrink-0" aria-hidden />
        Sync is off by default. Check the calendar module notes before you turn it on.
      </p>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={!changed || save.isPending}>
          Save calendar
        </Button>
        {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
      </FormActions>
    </form>
  );
}
