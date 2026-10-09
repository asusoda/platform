import { useQueryClient } from '@tanstack/react-query';
import { keyPath } from '../../lib/format';

// Refetches the knowledge queries and the overview after a change.
export function useInvalidate(prefix: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: ['knowledge', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
  };
}

// The dashboard path of the full text of a source. chunk marks a search result passage in it.
export function sourcePath(prefix: string, key: string, chunk?: string): string {
  return `/${prefix}/knowledge/sources/${keyPath(key)}${chunk ? `?chunk=${encodeURIComponent(chunk)}` : ''}`;
}
