import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Button, cx, Dialog, ErrorNote, FormActions, OkNote, SkeletonRows } from '../../components/ui';
import { send, api } from '../../lib/api';

type Role = { id: string; name: string; color: string };
type SyncCounts = { matched: number; new_users: number; joined: number; already: number };

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

// Adds the members of the org's Discord server, all or the holders of chosen roles, to the org's members.
export function DiscordSyncDialog({ prefix, open, onClose }: { prefix: string; open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [chosen, setChosen] = useState<string[]>([]);
  const roles = useQuery({
    queryKey: ['users', prefix, 'discord-roles'],
    queryFn: () => api<{ roles: Role[] }>(`/api/users/${prefix}/discord/roles`).then((body) => body.roles),
    enabled: open,
    staleTime: 300_000,
    retry: false,
  });
  const run = (dryRun: boolean) => send<SyncCounts>(`/api/users/${prefix}/discord/sync`, 'POST', { roles: chosen, dry_run: dryRun });
  const preview = useQuery({
    queryKey: ['users', prefix, 'discord-sync-preview', chosen.join(',')],
    queryFn: () => run(true),
    enabled: open,
    staleTime: 30_000,
    retry: false,
  });
  const sync = useMutation({
    mutationFn: () => run(false),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['points', prefix] });
      client.invalidateQueries({ queryKey: ['users', prefix, 'discord-sync-preview'] });
    },
  });
  const close = () => {
    sync.reset();
    setChosen([]);
    onClose();
  };
  const toggle = (id: string) => setChosen((current) => (current.includes(id) ? current.filter((r) => r !== id) : [...current, id]));
  const counts = preview.data;

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Add members from Discord"
      description="Adds people in the org's Discord server to its members, with their Discord name. Run it again at any time; members already added are kept as they are."
    >
      {sync.isSuccess ? (
        <div className="space-y-4">
          <OkNote>
            Added {plural(sync.data.joined, 'member')}
            {sync.data.new_users ? `, ${sync.data.new_users} of them new to Platform` : ''}. {sync.data.already} were members already.
          </OkNote>
          <Button onClick={close}>Close</Button>
        </div>
      ) : (
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            sync.mutate();
          }}
        >
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <p className="text-sm font-medium">Roles</p>
              {chosen.length ? (
                <button type="button" onClick={() => setChosen([])} className="cursor-pointer text-xs text-muted hover:text-fg">
                  Clear ({chosen.length})
                </button>
              ) : null}
            </div>
            <p className="text-xs text-muted">Pick roles to add only the people who hold one of them. With no role picked, everyone in the server is added. Bots are left out.</p>
            {roles.isPending ? (
              <SkeletonRows rows={3} />
            ) : roles.isError ? (
              <ErrorNote error={roles.error} />
            ) : (
              <div className="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto">
                {roles.data.map((role) => {
                  const on = chosen.includes(role.id);
                  return (
                    <button
                      key={role.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(role.id)}
                      className={cx(
                        'inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-md border px-2 text-xs transition-colors',
                        on ? 'border-accent bg-accent/10 text-fg' : 'border-line text-muted hover:bg-panel-2 hover:text-fg',
                      )}
                    >
                      <span className="size-2 rounded-full" style={{ backgroundColor: role.color === '#000000' ? 'var(--color-muted)' : role.color }} />
                      {role.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <div className="rounded-lg border border-line bg-panel-2/40 px-3 py-2.5 text-sm" aria-live="polite">
            {preview.isError ? (
              <span className="text-bad">{preview.error instanceof Error ? preview.error.message : 'The preview failed.'}</span>
            ) : !counts ? (
              <span className="text-muted">Counting server members...</span>
            ) : (
              <>
                <span className="font-medium">{plural(counts.joined, 'member')} to add</span>
                <span className="text-muted">
                  {' '}
                  of {counts.matched} {counts.matched === 1 ? 'person' : 'people'} who match. {counts.already} already members
                  {counts.new_users ? `, ${counts.new_users} new to Platform` : ''}.
                </span>
              </>
            )}
          </div>
          <FormActions error={sync.error}>
            <Button variant="primary" disabled={!counts || counts.joined === 0 || sync.isPending}>
              <RefreshCw className={cx('size-4', sync.isPending && 'animate-spin')} />
              {sync.isPending ? 'Adding...' : counts ? `Add ${plural(counts.joined, 'member')}` : 'Add members'}
            </Button>
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
          </FormActions>
        </form>
      )}
    </Dialog>
  );
}
