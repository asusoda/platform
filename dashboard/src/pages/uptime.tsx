import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HeartPulse, Pencil, Play, Plus } from 'lucide-react';
import { useState } from 'react';
import {
  Button,
  Card,
  CardHeader,
  DeleteButton,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  PageHeader,
  Select,
  SkeletonRows,
  Stat,
  StatGrid,
  Switch,
  Table,
  Td,
  Th,
  Tr,
  cx,
} from '../components/ui';
import { api, send } from '../lib/api';
import { type Tone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { UptimeCheck, UptimeMonitor, UptimeTarget } from '../lib/types';

// The number of checks in the bar of each monitor. The API sends the same number.
const BAR = 30;

type Draft = {
  name: string;
  target_kind: 'url' | 'app';
  target: string;
  expected_status: string;
  interval_minutes: string;
  timeout_seconds: string;
};

const EMPTY: Draft = { name: '', target_kind: 'url', target: '', expected_status: '2xx', interval_minutes: '5', timeout_seconds: '10' };

function draftOf(m: UptimeMonitor): Draft {
  return {
    name: m.name,
    target_kind: m.target_kind,
    target: m.target,
    expected_status: m.expected_status,
    interval_minutes: String(m.interval_minutes),
    timeout_seconds: String(m.timeout_seconds),
  };
}

function tone(m: UptimeMonitor): Tone {
  if (!m.enabled) return 'muted';
  if (m.state === 'up') return 'ok';
  if (m.state === 'down') return 'bad';
  return 'warn';
}

function percent(value: number | null): string {
  return value === null ? '-' : `${Number(value.toFixed(2))}%`;
}

function checkLabel(c: UptimeCheck): string {
  const result = c.up ? 'Up' : 'Down';
  const detail = c.error ?? (c.status_code ? `${c.status_code}` : '');
  const latency = c.latency_ms !== null ? `, ${c.latency_ms} ms` : '';
  return `${result} ${timeAgo(c.checked_at)}${detail ? `: ${detail}` : ''}${latency}`;
}

// The last checks as small bars, oldest on the left. Empty slots fill the left side.
function CheckBar({ checks }: { checks: UptimeCheck[] }) {
  const empty = Math.max(0, BAR - checks.length);
  return (
    <div className="flex h-6 items-stretch gap-[2px]" role="img" aria-label={`${checks.filter((c) => c.up).length} of ${checks.length} recent checks up`}>
      {Array.from({ length: empty }, (_, i) => (
        <span key={`e${i}`} className="w-1.5 rounded-[2px] bg-panel-2" />
      ))}
      {checks.map((c, i) => (
        <span key={`${c.checked_at}-${i}`} title={checkLabel(c)} className={cx('w-1.5 rounded-[2px]', c.up ? 'bg-ok/80' : 'bg-bad')} />
      ))}
    </div>
  );
}

function MonitorForm({
  prefix,
  monitor,
  open,
  onClose,
}: {
  prefix: string;
  monitor: UptimeMonitor | null;
  open: boolean;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>(monitor ? draftOf(monitor) : EMPTY);
  const targets = useQuery({
    queryKey: ['uptime', prefix, 'targets'],
    queryFn: () => api<{ apps: UptimeTarget[] }>(`/api/uptime/${prefix}/targets`),
    enabled: open && draft.target_kind === 'app',
  });
  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...draft,
        interval_minutes: Number(draft.interval_minutes),
        timeout_seconds: Number(draft.timeout_seconds),
      };
      return monitor
        ? send(`/api/uptime/${prefix}/monitors/${monitor.id}`, 'PUT', body)
        : send(`/api/uptime/${prefix}/monitors`, 'POST', body);
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['uptime', prefix] });
      onClose();
    },
  });
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const apps = targets.data?.apps ?? [];
  return (
    <Dialog open={open} onClose={onClose} title={monitor ? `Edit ${monitor.name}` : 'New monitor'}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="sm:col-span-2">
          <Field label="Name">
            <Input value={draft.name} onChange={set('name')} placeholder="Website" required />
          </Field>
        </div>
        <Field label="Checks">
          <Select value={draft.target_kind} onChange={(e) => setDraft({ ...draft, target_kind: e.target.value as Draft['target_kind'], target: '' })}>
            <option value="url">A URL</option>
            <option value="app">A Hosting app</option>
          </Select>
        </Field>
        <Field label="Expected status">
          <Input value={draft.expected_status} onChange={set('expected_status')} placeholder="2xx" required />
        </Field>
        <div className="sm:col-span-2">
          {draft.target_kind === 'url' ? (
            <Field label="URL">
              <Input type="url" value={draft.target} onChange={set('target')} placeholder="https://example.org/health" required />
            </Field>
          ) : (
            <Field label="App">
              <Select value={draft.target} onChange={set('target')} required>
                <option value="">{targets.isLoading ? 'Loading...' : apps.length ? 'Pick an app' : 'No apps'}</option>
                {apps.map((a) => (
                  <option key={a.name} value={a.name}>
                    {a.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>
        <Field label="Every (minutes)">
          <Input type="number" min={1} max={1440} value={draft.interval_minutes} onChange={set('interval_minutes')} />
        </Field>
        <Field label="Timeout (seconds)">
          <Input type="number" min={1} max={30} value={draft.timeout_seconds} onChange={set('timeout_seconds')} />
        </Field>
        <div className="sm:col-span-2">
          <FormActions error={save.error}>
            <Button variant="primary" disabled={save.isPending}>
              {monitor ? 'Save' : 'Add monitor'}
            </Button>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </FormActions>
        </div>
      </form>
    </Dialog>
  );
}

export function UptimePage() {
  const { prefix } = useCurrentOrg();
  const client = useQueryClient();
  // null: closed; 'new': a new monitor; a monitor: edit it
  const [editing, setEditing] = useState<UptimeMonitor | 'new' | null>(null);
  const monitors = useQuery({
    queryKey: ['uptime', prefix],
    queryFn: () => api<{ monitors: UptimeMonitor[] }>(`/api/uptime/${prefix}/monitors`),
    refetchInterval: 30_000,
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['uptime', prefix] });
  const toggle = useMutation({
    mutationFn: (m: UptimeMonitor) => send(`/api/uptime/${prefix}/monitors/${m.id}`, 'PUT', { enabled: !m.enabled }),
    onSuccess: refresh,
  });
  const check = useMutation({ mutationFn: (id: number) => send(`/api/uptime/${prefix}/monitors/${id}/check`, 'POST'), onSuccess: refresh });
  const remove = useMutation({ mutationFn: (id: number) => send(`/api/uptime/${prefix}/monitors/${id}`, 'DELETE'), onSuccess: refresh });
  const list = monitors.data?.monitors ?? [];
  const on = list.filter((m) => m.enabled);
  const add = (
    <Button variant="primary" onClick={() => setEditing('new')}>
      <Plus className="size-4" /> New monitor
    </Button>
  );
  const actionError = toggle.error ?? check.error ?? remove.error;

  return (
    <>
      <PageHeader title="Uptime" description="Checks of your sites and Hosting apps." action={add} />
      {list.length ? (
        <StatGrid className="mb-6">
          <Stat label="Up" value={on.filter((m) => m.state === 'up').length} />
          <Stat label="Down" value={on.filter((m) => m.state === 'down').length} />
          <Stat label="Paused" value={list.length - on.length} />
          <Stat label="Monitors" value={list.length} />
        </StatGrid>
      ) : null}
      {monitors.error || actionError ? (
        <div className="mb-4">
          <ErrorNote error={monitors.error ?? actionError} />
        </div>
      ) : null}
      <Card>
        <CardHeader title="Monitors" />
        {monitors.isLoading ? (
          <SkeletonRows />
        ) : list.length ? (
          <Table>
            <thead>
              <tr>
                <Th>Monitor</Th>
                <Th className="hidden lg:table-cell">Last {BAR} checks</Th>
                <Th className="text-right">24 h</Th>
                <Th className="hidden text-right sm:table-cell">7 days</Th>
                <Th className="hidden text-right md:table-cell">Latency</Th>
                <Th className="w-0" />
              </tr>
            </thead>
            <tbody>
              {list.map((m) => (
                <Tr key={m.id}>
                  <Td className="max-w-0 min-w-48">
                    <div className="flex items-center gap-2.5">
                      <Dot tone={tone(m)} />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{m.name}</div>
                        <div className="truncate text-xs text-muted">
                          {!m.enabled ? (
                            'Paused'
                          ) : m.state === 'down' && m.last_check?.error ? (
                            <span className="text-bad">{m.last_check.error}</span>
                          ) : (
                            <span className="font-mono">{m.target_kind === 'app' ? `app ${m.target}` : m.target}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </Td>
                  <Td className="hidden lg:table-cell">
                    <CheckBar checks={m.recent} />
                  </Td>
                  <Td className="text-right tabular-nums">{percent(m.uptime_24h)}</Td>
                  <Td className="hidden text-right tabular-nums sm:table-cell">{percent(m.uptime_7d)}</Td>
                  <Td className="hidden text-right text-muted tabular-nums md:table-cell">
                    {m.last_check?.latency_ms != null ? `${m.last_check.latency_ms} ms` : '-'}
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end gap-1">
                      <Switch checked={m.enabled} onChange={() => toggle.mutate(m)} label={`Monitor ${m.name} on`} />
                      <Button variant="ghost" size="icon" title="Check now" aria-label={`Check ${m.name} now`} disabled={check.isPending} onClick={() => check.mutate(m.id)}>
                        <Play className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Edit" aria-label={`Edit ${m.name}`} onClick={() => setEditing(m)}>
                        <Pencil className="size-4" />
                      </Button>
                      <DeleteButton label={`Delete ${m.name}`} question={`Delete monitor ${m.name} and its checks?`} onDelete={() => remove.mutate(m.id)} />
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState icon={HeartPulse} title="No monitors" action={add} />
        )}
      </Card>
      <MonitorForm
        key={editing === null ? 'closed' : editing === 'new' ? 'new' : editing.id}
        prefix={prefix}
        monitor={editing === 'new' ? null : editing}
        open={editing !== null}
        onClose={() => setEditing(null)}
      />
    </>
  );
}
