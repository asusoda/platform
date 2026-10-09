import { Plug } from 'lucide-react';
import { Link } from 'react-router';
import { useCurrentOrg } from '../lib/org';
import { useIntegrations } from '../lib/queries';

// A line that names the integrations this page needs and the org has not connected, with a link to connect them.
export function IntegrationHint({ keys }: { keys: string[] }) {
  const { prefix } = useCurrentOrg();
  const { data } = useIntegrations(prefix);
  const missing = (data?.integrations ?? []).filter((i) => keys.includes(i.key) && !i.source);
  if (!missing.length) return null;
  return (
    <Link
      to={`/${prefix}/integrations`}
      className="mb-4 flex animate-in items-center gap-3 rounded-lg border border-line bg-panel px-4 py-2.5 text-sm shadow-xs transition-colors hover:bg-panel-2/60"
    >
      <Plug className="size-4 shrink-0 text-warn" />
      <span className="min-w-0 flex-1">
        Connect {missing.map((i) => i.title).join(' and ')} to use this page.
      </span>
      <span className="text-xs text-muted">Integrations</span>
    </Link>
  );
}
