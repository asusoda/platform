import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal, Plus, X } from 'lucide-react';
import { type ComponentType, type ReactNode, useId, useRef, useState } from 'react';
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

// An editable list of Discord ids.
export function UsersEditor({ users, onChange }: { users: string[]; onChange: (users: string[]) => void }) {
  const [value, setValue] = useState('');
  const id = useId();
  const candidate = value.trim();
  const valid = isDiscordId(candidate);
  const add = () => {
    if (!valid) return;
    if (!users.includes(candidate)) onChange([...users, candidate]);
    setValue('');
  };
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium">
        Allowed members
      </label>
      <div className="flex gap-2">
        <Input
          id={id}
          value={value}
          inputMode="numeric"
          placeholder="Discord user id"
          className="font-mono"
          aria-invalid={Boolean(candidate) && !valid}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" onClick={add} disabled={!valid}>
          <Plus className="size-4" /> Add
        </Button>
      </div>
      <p className="text-xs text-muted">
        {candidate && !valid
          ? 'A Discord id is 5 to 25 digits. Copy it from Discord with developer mode on.'
          : 'Members listed here can connect even when the pod is not open to everyone.'}
      </p>
      {users.length ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Allowed members">
          {users.map((user) => (
            <li
              key={user}
              className="inline-flex h-7 items-center gap-1 rounded-md border border-line bg-panel-2 pr-0.5 pl-2 font-mono text-xs"
            >
              {user}
              <button
                type="button"
                aria-label={`Remove ${user}`}
                onClick={() => onChange(users.filter((u) => u !== user))}
                className="flex size-6 cursor-pointer items-center justify-center rounded text-muted hover:bg-panel hover:text-fg"
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
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
