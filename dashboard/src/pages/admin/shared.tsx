import { useQueryClient } from '@tanstack/react-query';
import { isBotDown } from '../../lib/queries';

const BOT_DOWN = 'The Discord bot is not available, so servers and roles cannot be read. Check that the bot process is running, then try again.';

// The error to show, with the bot message for a 503.
export const explain = (error: unknown) => (isBotDown(error) ? BOT_DOWN : error);

// Refetches the org lists, and the given org, after a change.
export function useRefreshOrgs() {
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
