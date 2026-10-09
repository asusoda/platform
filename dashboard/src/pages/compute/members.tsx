import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { Check, Plus, X } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import { Button, cx, Input, Select } from '../../components/ui';
import { ApiError, api } from '../../lib/api';
import { computePath, isDiscordId } from './shared';

type MemberHit = { id: string; name: string; username?: string | null; avatar?: string | null };
type MemberPage = { members: MemberHit[]; total: number };
type Role = { id: string; name: string; color: string };

const PAGE = 100;
// The most ids a pod lists; the same limit as MAX_ALLOWED_USERS in modules/compute/service.py.
const MAX_USERS = 500;

function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

function MemberAvatar({ hit }: { hit: MemberHit }) {
  if (hit.avatar) return <img src={hit.avatar} alt="" className="size-6 shrink-0 rounded-full" />;
  return (
    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-panel-2 text-[11px] font-medium text-muted uppercase">
      {hit.name.slice(0, 1)}
    </span>
  );
}

function membersQuery(path: string, query: string, role: string, limit: number) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query) params.set('q', query);
  if (role) params.set('role', role);
  return api<MemberPage>(`${path}?${params}`);
}

const errorText = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback);

// An editable list of Discord ids. Officers browse the server's members, filter by role or name, or paste an id.
export function UsersEditor({
  prefix,
  users,
  onChange,
}: {
  prefix: string;
  users: string[];
  onChange: (users: string[]) => void;
}) {
  const [value, setValue] = useState('');
  const [role, setRole] = useState('');
  const [active, setActive] = useState(0);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const id = useId();
  const candidate = value.trim();
  const typed = useDebounced(candidate, 250);
  const query = /^\d+$/.test(typed) ? '' : typed;
  const membersPath = `${computePath(prefix)}/members`;

  const roles = useQuery({
    queryKey: ['compute', prefix, 'member-roles'],
    queryFn: () => api<{ roles: Role[] }>(`/api/users/${prefix}/discord/roles`).then((body) => body.roles),
    enabled: Boolean(prefix),
    staleTime: 300_000,
    retry: false,
  });
  const list = useQuery({
    queryKey: ['compute', prefix, 'members', query, role],
    queryFn: () => membersQuery(membersPath, query, role, PAGE),
    enabled: Boolean(prefix),
    staleTime: 60_000,
    retry: false,
    placeholderData: keepPreviousData,
  });
  const unnamed = users.filter((user) => !picked[user]);
  const names = useQuery({
    queryKey: ['compute', prefix, 'member-names', unnamed.join(',')],
    queryFn: () =>
      api<{ members: MemberHit[] }>(`${membersPath}?ids=${unnamed.join(',')}`).then((body) =>
        Object.fromEntries(body.members.map((m) => [m.id, m.name])),
      ),
    enabled: Boolean(prefix) && unnamed.length > 0,
    staleTime: 300_000,
    retry: false,
  });
  const nameOf = (user: string): string | undefined => picked[user] ?? names.data?.[user];

  const hits = list.data?.members ?? [];
  const total = list.data?.total ?? 0;
  const roleName = roles.data?.find((r) => r.id === role)?.name;
  const remember = (members: MemberHit[]) =>
    setPicked((current) => ({ ...current, ...Object.fromEntries(members.map((m) => [m.id, m.name])) }));
  const add = (user: string, name?: string) => {
    if (!users.includes(user)) onChange([...users, user]);
    if (name) remember([{ id: user, name }]);
  };
  const toggle = (hit: MemberHit) => {
    if (users.includes(hit.id)) onChange(users.filter((u) => u !== hit.id));
    else add(hit.id, hit.name);
  };
  const addAll = useMutation({
    mutationFn: () => membersQuery(membersPath, query, role, MAX_USERS),
    onSuccess: (page) => {
      const fresh = page.members.filter((m) => !users.includes(m.id));
      remember(fresh);
      onChange([...users, ...fresh.map((m) => m.id)].slice(0, MAX_USERS));
    },
  });
  const rawId = isDiscordId(candidate);
  const settled = candidate === typed;

  let status = '';
  if (list.isError) status = errorText(list.error, 'The member list failed. Paste Discord ids.');
  else if (list.isPending || (list.isFetching && !hits.length)) status = 'Loading members...';
  else if (settled && !hits.length) status = query ? 'No member name starts with that.' : 'No members match.';
  else if (total > hits.length) status = `Showing ${hits.length} of ${total}. Type a name to narrow the list.`;
  else status = `${total} member${total === 1 ? '' : 's'}`;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="block text-sm font-medium">
          Allowed members
        </label>
        {users.length ? (
          <button type="button" onClick={() => onChange([])} className="cursor-pointer text-xs text-muted hover:text-fg">
            Clear all ({users.length})
          </button>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Select
          aria-label="Filter by role"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setActive(0);
          }}
          className="sm:w-48"
          disabled={roles.isError}
        >
          <option value="">{roles.isError ? 'Roles unavailable' : 'All roles'}</option>
          {(roles.data ?? []).map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
        <div className="flex flex-1 gap-2">
          <Input
            id={id}
            value={value}
            placeholder="Filter by name, or paste a Discord id"
            autoComplete="off"
            role="combobox"
            aria-expanded={hits.length > 0}
            aria-controls={`${id}-hits`}
            aria-activedescendant={hits[active] ? `${id}-hit-${hits[active].id}` : undefined}
            onChange={(e) => {
              setValue(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown' && hits.length) {
                e.preventDefault();
                setActive((i) => (i + 1) % hits.length);
              } else if (e.key === 'ArrowUp' && hits.length) {
                e.preventDefault();
                setActive((i) => (i - 1 + hits.length) % hits.length);
              } else if (e.key === 'Enter') {
                e.preventDefault();
                if (rawId) {
                  add(candidate);
                  setValue('');
                } else if (hits[active]) toggle(hits[active]);
              } else if (e.key === 'Escape' && value) {
                e.stopPropagation();
                setValue('');
              }
            }}
          />
          <Button type="button" onClick={() => {
              add(candidate);
              setValue('');
            }} disabled={!rawId} title="Add this Discord id">
            <Plus className="size-4" /> Add id
          </Button>
        </div>
      </div>
      <div className="rounded-lg border border-line bg-panel">
        {hits.length ? (
          <ul id={`${id}-hits`} role="listbox" aria-label="Server members" aria-multiselectable className="max-h-64 overflow-y-auto p-1">
            {hits.map((hit, i) => {
              const chosen = users.includes(hit.id);
              return (
                <li
                  key={hit.id}
                  id={`${id}-hit-${hit.id}`}
                  role="option"
                  aria-selected={chosen}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => toggle(hit)}
                  className={cx(
                    'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                    i === active && 'bg-panel-2',
                  )}
                >
                  <MemberAvatar hit={hit} />
                  <span className="truncate">{hit.name}</span>
                  {hit.username && hit.username !== hit.name ? (
                    <span className="truncate text-xs text-muted">@{hit.username}</span>
                  ) : null}
                  {chosen ? (
                    <span className="ml-auto inline-flex items-center gap-1 text-xs text-ok">
                      <Check className="size-3.5" /> Added
                    </span>
                  ) : (
                    <span className="ml-auto text-xs text-muted">Add</span>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}
        <div
          className={cx(
            'flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs',
            hits.length > 0 && 'border-t border-line',
            list.isError ? 'text-bad' : 'text-muted',
          )}
        >
          <span>{status}</span>
          {role && total > 0 && !list.isError ? (
            <Button type="button" variant="ghost" onClick={() => addAll.mutate()} disabled={addAll.isPending}>
              <Plus className="size-3.5" />
              {addAll.isPending ? 'Adding...' : `Add all ${Math.min(total, MAX_USERS)}${query ? ' shown' : ` in ${roleName ?? 'role'}`}`}
            </Button>
          ) : null}
        </div>
      </div>
      {addAll.isError ? <p className="text-xs text-bad">{errorText(addAll.error, 'Could not add the role.')}</p> : null}
      <p className="text-xs text-muted">
        Listed members can connect even when the pod is not open to everyone. The list keeps who you add, not the role.
      </p>
      {users.length ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Allowed members">
          {users.map((user) => {
            const name = nameOf(user);
            return (
              <li
                key={user}
                title={user}
                className={cx(
                  'inline-flex h-7 items-center gap-1 rounded-md border border-line bg-panel-2 pr-0.5 pl-2 text-xs',
                  !name && 'font-mono',
                )}
              >
                {name ?? user}
                <button
                  type="button"
                  aria-label={`Remove ${name ?? user}`}
                  onClick={() => onChange(users.filter((u) => u !== user))}
                  className="flex size-6 cursor-pointer items-center justify-center rounded text-muted hover:bg-panel hover:text-fg"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
