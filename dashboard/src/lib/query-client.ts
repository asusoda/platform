import { MutationCache, QueryCache, QueryClient, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { ApiError } from './api';
import { tokens } from './auth';
import { reportError } from './error-report';

// How long a fetched answer counts as fresh. A page opened again inside this time shows it with no request.
export const STALE_MS = 30_000;
// How long an answer that no page shows stays in memory, so going back to a page shows it at once.
export const GC_MS = 10 * 60_000;

// The one query client of the dashboard. The cache lives in memory only: answers hold member details, so they
// are not written to localStorage or sessionStorage.
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({ onError: (error, query) => reportError(error, `query ${String(query.queryKey[0])}`) }),
    mutationCache: new MutationCache({ onError: (error) => reportError(error, 'mutation') }),
    defaultOptions: {
      queries: {
        staleTime: STALE_MS,
        gcTime: GC_MS,
        // Pages with live data poll with refetchInterval. A focus change does not refetch every query at once.
        refetchOnWindowFocus: false,
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  });
}

// Signs out: drops the tokens and every cached answer, so the next officer in this tab sees none of them.
export function useSignOut(): () => void {
  const client = useQueryClient();
  const navigate = useNavigate();
  return () => {
    tokens.clear();
    client.clear();
    navigate('/login');
  };
}
