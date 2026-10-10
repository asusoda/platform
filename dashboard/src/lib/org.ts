import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router';
import { api } from './api';
import type { Organization } from './types';

export function useOrganizations() {
  return useQuery({ queryKey: ['organizations'], queryFn: () => api<Organization[]>('/api/organizations/') });
}

// The organization named by the :org route parameter.
export function useCurrentOrg(): { org: Organization | undefined; prefix: string; isLoading: boolean } {
  const { org: prefix = '' } = useParams();
  const { data, isLoading } = useOrganizations();
  return { org: data?.find((o) => o.prefix === prefix), prefix, isLoading };
}
