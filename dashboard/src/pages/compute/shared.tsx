import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal, Plus, X } from 'lucide-react';
import { type ComponentType, type ReactNode, useEffect, useId, useRef, useState } from 'react';
import { Button, cx, Input } from '../../components/ui';
import { ApiError, api, send } from '../../lib/api';
import type { Tone } from '../../lib/format';
import type { Pod } from '../../lib/types';

export const computePath = (prefix: string) => `/api/compute/${prefix}`;
export const podPath = (prefix: string, podId: string) => `${computePath(prefix)}/pods/${encodeURIComponent(podId)}`;
export const podsKey = (prefix: string) => ['compute', prefix, 'pods'];

export function usePods(prefix: string) {
  return useQuery({
    queryKey: podsKey(prefix),
    queryFn: () => api<{ pods: Pod[] }>(`${computePath(prefix)}/pods`).then((body) => body.pods),
    enabled: Boolean(prefix),
    refetchInterval: 15_000,
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  });
}

// Refetches the pod list and the overview after a change.
export function useRefreshCompute(prefix: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: ['compute', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
  };
}

export type PodAction = 'start' | 'stop' | 'restart' | 'terminate';

export function usePodAction(prefix: string, podId: string) {
  const refresh = useRefreshCompute(prefix);
  return useMutation({
    mutationFn: (action: PodAction) => send(`${podPath(prefix, podId)}/action`, 'POST', { action }),
    onSuccess: refresh,
  });
}

// True when the pod list failed because the org has no RunPod key.
export function isMissingKey(error: unknown): boolean {
  return error instanceof ApiError && error.status === 400 && error.message.includes('runpod_api_key');
}

export function statusTone(status: string | null): Tone {
  if (status === 'RUNNING') return 'ok';
  if (status === 'EXITED' || status === 'STOPPED') return 'muted';
  if (status === 'GONE' || status === 'TERMINATED' || status === 'FAILED') return 'bad';
  if (status === 'UNKNOWN' || !status) return 'warn';
  return 'active';
}

export function statusLabel(status: string | null): string {
  if (!status) return 'Unknown';
  if (status === 'EXITED') return 'Stopped';
  return status.charAt(0) + status.slice(1).toLowerCase();
}

const text = (value: unknown) => (typeof value === 'string' && value ? value : null);

// A short name for the hardware RunPod placed the pod on.
export function machineLabel(machine: Record<string, unknown> | null): string | null {
  if (!machine) return null;
  const gpuType = machine.gpuType as Record<string, unknown> | undefined;
  return (
    text(gpuType?.displayName) ??
    text(machine.gpuDisplayName) ??
    text(machine.gpuTypeId) ??
    text(machine.cpuTypeId) ??
    text(machine.location) ??
    text(machine.dataCenterId)
  );
}

export function costLabel(cost: number | string | null): string | null {
  const value = typeof cost === 'string' ? Number(cost) : cost;
  if (value === null || !Number.isFinite(value)) return null;
  return `$${value.toFixed(value > 0 && value < 0.1 ? 3 : 2)}/hr`;
}

export const isDiscordId = (value: string) => /^\d{5,25}$/.test(value);

type MemberHit = { id: string; name: string; username?: string | null; avatar?: string | null };

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

// An editable list of Discord ids. Officers search server members by name, or paste an id.
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
  const [active, setActive] = useState(0);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const id = useId();
  const candidate = value.trim();
  const query = useDebounced(candidate, 250);
  const searchable = query.length >= 2 && !/^\d+$/.test(query);
  const membersPath = `${computePath(prefix)}/members`;

  const search = useQuery({
    queryKey: ['compute', prefix, 'members', query],
    queryFn: () =>
      api<{ members: MemberHit[] }>(`${membersPath}?q=${encodeURIComponent(query)}`).then((body) => body.members),
    enabled: Boolean(prefix) && searchable,
    staleTime: 30_000,
    retry: false,
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

  const hits = searchable && candidate === query ? (search.data ?? []).filter((m) => !users.includes(m.id)) : [];
  const add = (user: string, name?: string) => {
    if (!users.includes(user)) onChange([...users, user]);
    if (name) setPicked((current) => ({ ...current, [user]: name }));
    setValue('');
    setActive(0);
  };
  const rawId = isDiscordId(candidate);

  let hint = 'Search the server by name, or paste a Discord id. Listed members can connect even when the pod is not open to everyone.';
  if (search.isError) hint = search.error instanceof ApiError ? search.error.message : 'The member search failed.';
  else if (searchable && search.isFetching && !hits.length) hint = 'Searching...';
  else if (searchable && candidate === query && search.isSuccess && !hits.length) hint = 'No member name starts with that. Search by username or server nickname.';
  else if (/^\d+$/.test(candidate) && !rawId) hint = 'A Discord id is 5 to 25 digits.';

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium">
        Allowed members
      </label>
      <div className="flex gap-2">
        <Input
          id={id}
          value={value}
          placeholder="Search by name, or paste a Discord id"
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
              const hit = hits[active];
              if (hit) add(hit.id, hit.name);
              else if (rawId) add(candidate);
            } else if (e.key === 'Escape' && value) {
              e.stopPropagation();
              setValue('');
            }
          }}
        />
        <Button type="button" onClick={() => add(candidate)} disabled={!rawId} title="Add this Discord id">
          <Plus className="size-4" /> Add
        </Button>
      </div>
      {hits.length ? (
        <ul id={`${id}-hits`} role="listbox" aria-label="Matching members" className="rounded-lg border border-line bg-panel p-1">
          {hits.map((hit, i) => (
            <li
              key={hit.id}
              id={`${id}-hit-${hit.id}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => add(hit.id, hit.name)}
              className={cx(
                'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                i === active ? 'bg-panel-2 text-fg' : 'text-fg',
              )}
            >
              <MemberAvatar hit={hit} />
              <span className="truncate">{hit.name}</span>
              {hit.username && hit.username !== hit.name ? (
                <span className="truncate text-xs text-muted">@{hit.username}</span>
              ) : null}
              <span className="ml-auto text-xs text-muted">Add</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className={cx('text-xs', search.isError ? 'text-bad' : 'text-muted')}>{hint}</p>
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

// A dropdown of row actions on the popover API, so table and card overflow do not clip it.
export function RowMenu({ label, children }: { label: string; children: (close: () => void) => ReactNode }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const close = () => menu.current?.hidePopover();
  return (
    <>
      <Button ref={button} variant="ghost" size="icon" aria-label={label} title="More" popoverTarget={id}>
        <MoreHorizontal className="size-4" />
      </Button>
      <div
        ref={menu}
        id={id}
        popover="auto"
        onToggle={(e) => {
          if (e.newState !== 'open' || !button.current || !menu.current) return;
          const rect = button.current.getBoundingClientRect();
          const below = window.innerHeight - rect.bottom > menu.current.offsetHeight + 8;
          menu.current.style.top = below ? `${rect.bottom + 4}px` : `${rect.top - menu.current.offsetHeight - 4}px`;
          menu.current.style.left = `${Math.max(8, rect.right - menu.current.offsetWidth)}px`;
          window.addEventListener('scroll', close, { once: true, capture: true });
          menu.current.querySelector('button')?.focus();
        }}
        className="m-0 min-w-44 rounded-lg border border-line bg-panel p-1 text-fg shadow-lg"
      >
        {children(close)}
      </div>
    </>
  );
}

export function MenuItem({
  icon: Icon,
  danger,
  className,
  children,
  onClick,
  disabled,
}: {
  icon: ComponentType<{ className?: string }>;
  danger?: boolean;
  className?: string;
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cx(
        'flex h-8 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-left text-sm transition-colors outline-none focus-visible:bg-panel-2 disabled:pointer-events-none disabled:opacity-50',
        danger ? 'text-bad hover:bg-bad/10 focus-visible:bg-bad/10' : 'hover:bg-panel-2',
        className,
      )}
    >
      <Icon className="size-4 shrink-0 opacity-80" />
      {children}
    </button>
  );
}

export function MenuSeparator() {
  return <div role="separator" className="my-1 h-px bg-line" />;
}

export type ComputeSettings = { pod_image: string | null; deployment_pod_image: string };

export function useComputeSettings(prefix: string) {
  return useQuery({
    queryKey: ['compute', prefix, 'settings'],
    queryFn: () => api<{ settings: ComputeSettings }>(`${computePath(prefix)}/settings`).then((body) => body.settings),
    enabled: Boolean(prefix),
  });
}
