import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, CircleCheck, Plus, Server, ShieldCheck, Trash2, Unplug, UserCog, UserX } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { ActivityList } from '../components/activity-list';
import { OrgMark } from '../components/org-mark';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Code,
  Dialog,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  PageSkeleton,
  Select,
  SkeletonRows,
  Stat,
  Table,
  Td,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { useCurrentOrg, useOrganizations } from '../lib/org';
import { isBotDown, useSuperadmin } from '../lib/queries';
import type { AuditEntry, AvailableGuild, GuildRole, OrganizationDetail, SuperadminDashboard } from '../lib/types';

const PAGE = 50;
const BOT_DOWN = 'The Discord bot is not available, so servers and roles cannot be read. Check that the bot process is running, then try again.';

// The error to show, with the bot message for a 503.
const explain = (error: unknown) => (isBotDown(error) ? BOT_DOWN : error);

// The prefix the server gives a new organization, from prefix_for in modules/superadmin/service.py.
function prefixFor(name: string, guildId: string): string {
  const prefix = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 20).replace(/_+$/, '');
  return prefix.length >= 2 ? prefix : `org_${guildId.slice(-6)}`;
}

function useRefreshOrgs() {
  const client = useQueryClient();
  return (org?: { id: number; prefix: string }) => {
    client.invalidateQueries({ queryKey: ['superadmin-dashboard'] });
    client.invalidateQueries({ queryKey: ['organizations'] });
    if (org) {
      client.invalidateQueries({ queryKey: ['organization', org.id] });
      client.invalidateQueries({ queryKey: ['overview', org.prefix] });
    }
  };
}

function OfficerRoleDialog({ org, onClose }: { org: OrganizationDetail; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const [role, setRole] = useState(org.officer_role_id ?? '');
  const roles = useQuery({
    queryKey: ['guild-roles', org.guild_id],
    queryFn: () => api<{ roles: GuildRole[] }>(`/api/superadmin/guild_roles/${org.guild_id}`),
    retry: false,
  });
  const save = useMutation({
    mutationFn: () => send(`/api/superadmin/update_officer_role/${org.id}`, 'PUT', { officer_role_id: role }),
    onSuccess: () => {
      refresh(org);
      onClose();
    },
  });
  const list = roles.data?.roles ?? [];
  const unknown = role && roles.data && !list.some((r) => r.id === role);
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {roles.error ? <ErrorNote error={explain(roles.error)} /> : null}
      <Field label="Officer role" hint="Members with this role can use the dashboard for this organization.">
        <Select value={role} onChange={(e) => setRole(e.target.value)} disabled={!roles.data}>
          <option value="">{roles.isLoading ? 'Loading roles...' : 'No officer role'}</option>
          {unknown ? <option value={role}>Unknown role {role}</option> : null}
          {list.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </Field>
      {role ? (
        <p className="text-xs text-muted">
          Role ID <Code>{role}</Code>
        </p>
      ) : (
        <p className="text-xs text-muted">With no officer role, no member can open this organization in the dashboard.</p>
      )}
      <FormActions error={save.error ? explain(save.error) : undefined}>
        <Button variant="primary" disabled={!roles.data || role === (org.officer_role_id ?? '') || save.isPending}>
          Save role
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function RemoveDialog({ org, onClose }: { org: OrganizationDetail; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const navigate = useNavigate();
  const { prefix } = useCurrentOrg();
  const [typed, setTyped] = useState('');
  const remove = useMutation({
    mutationFn: () => send(`/api/superadmin/remove_org/${org.id}`, 'DELETE'),
    onSuccess: () => {
      refresh(org);
      onClose();
      if (org.prefix === prefix) navigate('/');
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (typed === org.prefix) remove.mutate();
      }}
    >
      <div className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-pretty text-bad">
        This deletes <strong className="font-semibold">{org.name}</strong> and its settings. You cannot undo it.
      </div>
      <Field label={`Type ${org.prefix} to confirm`}>
        <Input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          className="font-mono"
          placeholder={org.prefix}
        />
      </Field>
      <FormActions error={remove.error}>
        <Button variant="danger" disabled={typed !== org.prefix || remove.isPending}>
          Remove organization
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function AddDialog({ guild, onClose }: { guild: AvailableGuild; onClose: () => void }) {
  const refresh = useRefreshOrgs();
  const add = useMutation({
    mutationFn: () => send(`/api/superadmin/add_org/${guild.id}`, 'POST'),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 text-sm">
        <dt className="text-muted">Server</dt>
        <dd className="truncate font-medium">{guild.name}</dd>
        <dt className="text-muted">Server ID</dt>
        <dd>
          <Mono>{guild.id}</Mono>
        </dd>
        <dt className="text-muted">Prefix</dt>
        <dd>
          <Code>{prefixFor(guild.name, guild.id)}</Code>
        </dd>
      </dl>
      <p className="text-xs text-pretty text-muted">
        The organization starts with default settings and no officer role. Set the officer role next so officers can sign in.
      </p>
      <FormActions error={add.error ? explain(add.error) : undefined}>
        <Button variant="primary" onClick={() => add.mutate()} disabled={add.isPending}>
          Add organization
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </div>
  );
}

function OrganizationsCard({
  orgs,
  onRole,
  onRemove,
}: {
  orgs: OrganizationDetail[];
  onRole: (org: OrganizationDetail) => void;
  onRemove: (org: OrganizationDetail) => void;
}) {
  if (!orgs.length) {
    return (
      <EmptyState icon={Building2} title="No organizations">
        Add one from a Discord server below.
      </EmptyState>
    );
  }
  return (
    <Table>
      <thead>
        <tr>
          <Th>Organization</Th>
          <Th className="hidden lg:table-cell">Server ID</Th>
          <Th className="hidden sm:table-cell">Officer role</Th>
          <Th className="hidden md:table-cell">Status</Th>
          <Th>
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {orgs.map((o) => (
          <Tr key={o.id}>
            <Td className="w-full max-w-0 py-2.5">
              <div className="flex items-center gap-3">
                <OrgMark name={o.name} logoUrl={o.icon_url} className="size-7" />
                <div className="min-w-0">
                  {o.is_active ? (
                    <Link to={`/${o.prefix}`} className="block truncate font-medium hover:underline">
                      {o.name}
                    </Link>
                  ) : (
                    <span className="block truncate font-medium">{o.name}</span>
                  )}
                  <span className="flex items-center gap-2">
                    <Mono className="truncate">{o.prefix}</Mono>
                    {o.is_active ? null : <Badge className="md:hidden">Inactive</Badge>}
                  </span>
                </div>
              </div>
            </Td>
            <Td className="hidden whitespace-nowrap lg:table-cell">
              <Mono>{o.guild_id}</Mono>
            </Td>
            <Td className="hidden whitespace-nowrap sm:table-cell">
              {o.officer_role_id ? <Mono>{o.officer_role_id}</Mono> : <Badge tone="warn">Not set</Badge>}
            </Td>
            <Td className="hidden md:table-cell">
              <Badge tone={o.is_active ? 'ok' : 'muted'}>{o.is_active ? 'Active' : 'Inactive'}</Badge>
            </Td>
            <Td>
              <div className="flex justify-end gap-2">
                <Button onClick={() => onRole(o)} aria-label={`Set officer role for ${o.name}`}>
                  <UserCog className="size-4" />
                  <span className="hidden sm:inline">Officer role</span>
                </Button>
                <Button variant="danger" size="icon" onClick={() => onRemove(o)} aria-label={`Remove ${o.name}`} title="Remove">
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}

function GuildsCard({ guilds, onAdd }: { guilds: AvailableGuild[]; onAdd: (guild: AvailableGuild) => void }) {
  if (!guilds.length) {
    return (
      <EmptyState icon={Server} title="Every server has an organization">
        Invite the bot to a Discord server to add it here.
      </EmptyState>
    );
  }
  const counts = guilds.some((g) => typeof g.member_count === 'number');
  return (
    <Table>
      <thead>
        <tr>
          <Th>Server</Th>
          <Th className="hidden md:table-cell">Server ID</Th>
          {counts ? <Th className="hidden text-right sm:table-cell">Members</Th> : null}
          <Th>
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {guilds.map((g) => (
          <Tr key={g.id}>
            <Td className="w-full max-w-0 py-2.5">
              <div className="flex items-center gap-3">
                <OrgMark name={g.name} logoUrl={g.icon?.url} className="size-7" />
                <div className="min-w-0">
                  <span className="block truncate font-medium">{g.name}</span>
                  <Mono className="block truncate md:hidden">{g.id}</Mono>
                </div>
              </div>
            </Td>
            <Td className="hidden whitespace-nowrap md:table-cell">
              <Mono>{g.id}</Mono>
            </Td>
            {counts ? (
              <Td className="hidden text-right text-muted tabular-nums sm:table-cell">{g.member_count ?? '-'}</Td>
            ) : null}
            <Td className="text-right">
              <Button onClick={() => onAdd(g)} aria-label={`Add ${g.name} as an organization`}>
                <Plus className="size-4" />
                <span className="hidden sm:inline">Add</span>
              </Button>
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}

function AuditCard({ prefixes }: { prefixes: string[] }) {
  const [org, setOrg] = useState('');
  const log = useInfiniteQuery({
    queryKey: ['superadmin-audit', org],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(PAGE) });
      if (org) params.set('org', org);
      if (pageParam) params.set('before_id', String(pageParam));
      return api<{ entries: AuditEntry[] }>(`/api/superadmin/audit?${params}`);
    },
    getNextPageParam: (last) => (last.entries.length === PAGE ? last.entries[last.entries.length - 1].id : undefined),
  });
  const entries = log.data?.pages.flatMap((p) => p.entries) ?? [];
  return (
    <>
      <Card>
        <CardHeader
          title="Audit log"
          hint="Every change across all organizations, newest first."
          action={
            <Select value={org} onChange={(e) => setOrg(e.target.value)} aria-label="Filter by organization" className="h-8 w-40 text-xs sm:w-48">
              <option value="">All organizations</option>
              {prefixes.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          }
        />
        {log.error ? (
          <div className="p-4">
            <ErrorNote error={log.error} />
          </div>
        ) : log.isLoading ? (
          <SkeletonRows rows={6} />
        ) : (
          <ActivityList entries={entries} empty="Nothing recorded yet." showOrg={!org} />
        )}
      </Card>
      {log.hasNextPage ? (
        <div className="mt-4 flex justify-center">
          <Button onClick={() => log.fetchNextPage()} disabled={log.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      ) : null}
    </>
  );
}

type Open = { kind: 'role' | 'remove'; org: OrganizationDetail } | { kind: 'add'; guild: AvailableGuild } | null;

function Superadmin() {
  const [open, setOpen] = useState<Open>(null);
  const orgList = useOrganizations();
  const dashboard = useQuery({
    queryKey: ['superadmin-dashboard'],
    queryFn: () => api<SuperadminDashboard>('/api/superadmin/dashboard'),
    retry: (count, error) => !isBotDown(error) && count < 2,
  });
  const orgs = dashboard.data?.existing_orgs ?? [];
  const guilds = dashboard.data?.available_guilds ?? [];
  const prefixes = (dashboard.data ? orgs : (orgList.data ?? [])).map((o) => o.prefix).sort();
  const close = () => setOpen(null);
  return (
    <>
      <PageHeader title="Superadmin" description="Organizations on this Platform, the Discord servers the bot is in, and the audit log for all of them." />

      {dashboard.error ? (
        <Card className="mb-6">
          {isBotDown(dashboard.error) ? (
            <EmptyState
              icon={Unplug}
              title="Discord bot not available"
              action={
                <Button onClick={() => dashboard.refetch()} disabled={dashboard.isFetching}>
                  Try again
                </Button>
              }
            >
              Organizations and servers come from the bot. Check that the bot process is running, then try again.
            </EmptyState>
          ) : (
            <div className="p-4">
              <ErrorNote error={dashboard.error} />
            </div>
          )}
        </Card>
      ) : null}

      {dashboard.data ? (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Organizations" value={orgs.length} icon={<Building2 className="size-4" />} />
          <Stat label="Active" value={orgs.filter((o) => o.is_active).length} icon={<CircleCheck className="size-4" />} />
          <Stat label="No officer role" value={orgs.filter((o) => !o.officer_role_id).length} icon={<UserX className="size-4" />} />
          <Stat label="Servers to add" value={guilds.length} icon={<Server className="size-4" />} />
        </div>
      ) : null}

      {!dashboard.error ? (
        <div className="mb-6 space-y-6">
          <Card>
            <CardHeader title="Organizations" hint="Set who counts as an officer, or remove an organization." />
            {dashboard.isLoading ? (
              <SkeletonRows />
            ) : (
              <OrganizationsCard orgs={orgs} onRole={(org) => setOpen({ kind: 'role', org })} onRemove={(org) => setOpen({ kind: 'remove', org })} />
            )}
          </Card>
          <Card>
            <CardHeader title="Discord servers without an organization" hint="Servers the bot is in that have no organization yet." />
            {dashboard.isLoading ? <SkeletonRows rows={2} /> : <GuildsCard guilds={guilds} onAdd={(guild) => setOpen({ kind: 'add', guild })} />}
          </Card>
        </div>
      ) : null}

      <AuditCard prefixes={prefixes} />

      <Dialog open={open?.kind === 'role'} onClose={close} title="Officer role" description={open?.kind === 'role' ? open.org.name : undefined}>
        {open?.kind === 'role' ? <OfficerRoleDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'remove'} onClose={close} title="Remove organization" description={open?.kind === 'remove' ? open.org.name : undefined}>
        {open?.kind === 'remove' ? <RemoveDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'add'} onClose={close} title="Add organization" description="Create an organization for this Discord server.">
        {open?.kind === 'add' ? <AddDialog key={open.guild.id} guild={open.guild} onClose={close} /> : null}
      </Dialog>
    </>
  );
}

export function AdminPage() {
  const superadmin = useSuperadmin();
  if (superadmin.isLoading) return <PageSkeleton stats />;
  if (superadmin.error) return <ErrorNote error={superadmin.error} />;
  if (!superadmin.data) {
    return (
      <>
        <PageHeader title="Superadmin" />
        <Card>
          <EmptyState icon={ShieldCheck} title="Superadmin only">
            Only the Platform superadmin can manage organizations and see the audit log for all of them.
          </EmptyState>
        </Card>
      </>
    );
  }
  return <Superadmin />;
}
