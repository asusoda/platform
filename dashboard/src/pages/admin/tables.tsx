import { Building2, Plus, Server, Trash2, UserCog } from 'lucide-react';
import { Link } from 'react-router';
import { OrgMark } from '../../components/org-mark';
import { Badge, Button, EmptyState, Mono, Table, Td, Th, Tr } from '../../components/ui';
import type { AvailableGuild, OrganizationDetail } from '../../lib/types';

export function OrganizationsCard({
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

export function GuildsCard({ guilds, onAdd }: { guilds: AvailableGuild[]; onAdd: (guild: AvailableGuild) => void }) {
  if (!guilds.length) {
    return (
      <EmptyState icon={Server} title="Every server has an org">
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
