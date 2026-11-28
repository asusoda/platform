import { Plug } from 'lucide-react';
import { useCurrentOrg } from '../lib/org';
import { useIntegrations } from '../lib/queries';
import { BannerLink } from './ui';

// A line that names the integrations this page needs and the org has not connected, with a link to connect them.
export function IntegrationHint({ keys }: { keys: string[] }) {
  const { prefix } = useCurrentOrg();
  const { data } = useIntegrations(prefix);
  const missing = (data?.integrations ?? []).filter((i) => keys.includes(i.key) && !i.source);
  if (!missing.length) return null;
  return (
    <BannerLink to={`/${prefix}/explore?tab=integrations`} icon={Plug} label="Integrations">
      Connect {missing.map((i) => i.title).join(' and ')} to use this page.
    </BannerLink>
  );
}
