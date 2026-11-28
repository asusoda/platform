import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { isBotDown } from '../../lib/queries';
import type { SuperadminOrg } from '../../lib/types';

const BOT_DOWN = 'The Discord bot is not available, so servers and roles cannot be read. Check that the bot process is running, then try again.';

// The error to show, with the bot message for a 503.
export const explain = (error: unknown) => (isBotDown(error) ? BOT_DOWN : error);

export const ORGS_KEY = ['superadmin-orgs'];

// Every org, from the database. It needs no bot.
export function useAdminOrgs() {
  return useQuery({ queryKey: ORGS_KEY, queryFn: () => api<{ orgs: SuperadminOrg[] }>('/api/superadmin/orgs').then((b) => b.orgs) });
}

// The prefixes of every org, sorted, for the org filters.
export function useOrgPrefixes(): string[] {
  return (useAdminOrgs().data ?? []).map((o) => o.prefix).sort();
}

// Refetches the org lists, and the given org, after a change.
export function useRefreshOrgs() {
  const client = useQueryClient();
  return (org?: { id: number; prefix: string }) => {
    client.invalidateQueries({ queryKey: ORGS_KEY });
    client.invalidateQueries({ queryKey: ['superadmin-dashboard'] });
    client.invalidateQueries({ queryKey: ['organizations'] });
    if (org) {
      client.invalidateQueries({ queryKey: ['organization', org.id] });
      client.invalidateQueries({ queryKey: ['overview', org.prefix] });
    }
  };
}
