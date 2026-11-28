import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Building2, Plus, Server, Trash2, Unplug, UserCog } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { OrgMark } from '../../components/org-mark';
import { Badge, Button, Card, CardHeader, Dialog, EmptyState, ErrorNote, Mono, PageHeader, SkeletonRows, Table, Td, Th, Tr } from '../../components/ui';
import { api } from '../../lib/api';
import { isBotDown } from '../../lib/queries';
import type { AvailableGuild, SuperadminDashboard, SuperadminOrg } from '../../lib/types';
import { AddDialog, OfficerRoleDialog, RemoveDialog } from './dialogs';
import { useAdminOrgs } from './shared';

type Open = { kind: 'role' | 'remove'; org: SuperadminOrg } | { kind: 'add'; guild: AvailableGuild } | null;

const openLink =
  'inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-panel-2 hover:text-fg';

function OrgTable({ orgs, onRole, onRemove }: { orgs: SuperadminOrg[]; onRole: (org: SuperadminOrg) => void; onRemove: (org: SuperadminOrg) => void }) {
  if (!orgs.length) return <EmptyState icon={Building2} title="No organizations" />;
  return (
    <Table>
      <thead>
        <tr>
          <Th>Organization</Th>
          <Th className="hidden text-right sm:table-cell">Members</Th>
          <Th className="hidden text-right lg:table-cell">Modules</Th>
          <Th className="hidden md:table-cell">Officer role</Th>
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
                  <span className="block truncate font-medium">{o.name}</span>
                  <span className="flex items-center gap-2">
                    <Mono className="truncate">{o.prefix}</Mono>
                    {o.is_active ? null : <Badge className="md:hidden">Inactive</Badge>}
                    {o.near.length ? <Badge tone="warn">Near {o.near.length === 1 ? 'a limit' : `${o.near.length} limits`}</Badge> : null}
                  </span>
                </div>
              </div>
            </Td>
            <Td className="hidden text-right text-muted tabular-nums sm:table-cell">{o.members}</Td>
            <Td className="hidden text-right text-muted tabular-nums lg:table-cell">{o.modules_on.length}</Td>
            <Td className="hidden whitespace-nowrap md:table-cell">
              {o.officer_role_id ? <Mono>{o.officer_role_id}</Mono> : <Badge tone="warn">Not set</Badge>}
            </Td>
            <Td className="hidden md:table-cell">
              <Badge tone={o.is_active ? 'ok' : 'muted'}>{o.is_active ? 'Active' : 'Inactive'}</Badge>
            </Td>
            <Td>
              <div className="flex justify-end gap-1">
                <Button variant="ghost" size="icon" onClick={() => onRole(o)} aria-label={`Set officer role for ${o.name}`} title="Officer role">
                  <UserCog className="size-4" />
                </Button>
                <Button variant="ghost" size="icon" className="hover:text-bad" onClick={() => onRemove(o)} aria-label={`Remove ${o.name}`} title="Remove">
                  <Trash2 className="size-4" />
                </Button>
                {o.is_active ? (
                  <Link to={`/${o.prefix}`} className={openLink} aria-label={`Open ${o.name}`} title="Open">
                    <ArrowRight className="size-4" />
                  </Link>
                ) : (
                  <span className="size-8" aria-hidden />
                )}
              </div>
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}

function GuildTable({ guilds, onAdd }: { guilds: AvailableGuild[]; onAdd: (guild: AvailableGuild) => void }) {
  if (!guilds.length) return <EmptyState icon={Server} title="Every server has an org" />;
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
            {counts ? <Td className="hidden text-right text-muted tabular-nums sm:table-cell">{g.member_count ?? '-'}</Td> : null}
            <Td className="text-right">
              <Button onClick={() => onAdd(g)} aria-label={`Add ${g.name} as an org`}>
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

// Every org, from the database, and the Discord servers with no org, from the bot.
export function OrganizationsPage() {
  const [open, setOpen] = useState<Open>(null);
  const orgs = useAdminOrgs();
  const guilds = useQuery({
    queryKey: ['superadmin-dashboard'],
    queryFn: () => api<SuperadminDashboard>('/api/superadmin/dashboard'),
    retry: (count, error) => !isBotDown(error) && count < 2,
  });
  const close = () => setOpen(null);
  return (
    <>
      <PageHeader title="Organizations" />
      <div className="space-y-6">
        <Card>
          <CardHeader title={orgs.data ? `${orgs.data.length} ${orgs.data.length === 1 ? 'organization' : 'organizations'}` : 'Organizations'} />
          {orgs.error ? (
            <div className="p-4">
              <ErrorNote error={orgs.error} />
            </div>
          ) : orgs.isLoading ? (
            <SkeletonRows />
          ) : (
            <OrgTable orgs={orgs.data ?? []} onRole={(org) => setOpen({ kind: 'role', org })} onRemove={(org) => setOpen({ kind: 'remove', org })} />
          )}
        </Card>
        <Card>
          <CardHeader title="Discord servers without an org" />
          {guilds.error ? (
            isBotDown(guilds.error) ? (
              <EmptyState
                icon={Unplug}
                title="Discord bot not available"
                action={
                  <Button onClick={() => guilds.refetch()} disabled={guilds.isFetching}>
                    Try again
                  </Button>
                }
              />
            ) : (
              <div className="p-4">
                <ErrorNote error={guilds.error} />
              </div>
            )
          ) : guilds.isLoading ? (
            <SkeletonRows rows={2} />
          ) : (
            <GuildTable guilds={guilds.data?.available_guilds ?? []} onAdd={(guild) => setOpen({ kind: 'add', guild })} />
          )}
        </Card>
      </div>

      <Dialog open={open?.kind === 'role'} onClose={close} title="Officer role" description={open?.kind === 'role' ? open.org.name : undefined}>
        {open?.kind === 'role' ? <OfficerRoleDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'remove'} onClose={close} title="Remove org" description={open?.kind === 'remove' ? open.org.name : undefined}>
        {open?.kind === 'remove' ? <RemoveDialog key={open.org.id} org={open.org} onClose={close} /> : null}
      </Dialog>
      <Dialog open={open?.kind === 'add'} onClose={close} title="Add org" description="Make an org for this Discord server.">
        {open?.kind === 'add' ? <AddDialog key={open.guild.id} guild={open.guild} onClose={close} /> : null}
      </Dialog>
    </>
  );
}
