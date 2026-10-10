import { useQueryClient } from '@tanstack/react-query';

// Refetches the knowledge queries and the overview after a change.
export function useInvalidate(prefix: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: ['knowledge', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
  };
}
