import { type QueryClient, queryOptions, useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { Order, Product } from '../../lib/types';

const productsQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['store', prefix, 'products'],
    queryFn: () => api<Product[]>(`/api/storefront/${prefix}/products`),
    enabled: Boolean(prefix),
  });

const ordersQuery = (prefix: string) =>
  queryOptions({
    queryKey: ['store', prefix, 'orders'],
    queryFn: () => api<Order[]>(`/api/storefront/${prefix}/orders`),
    enabled: Boolean(prefix),
  });

// Starts both Store requests, for a sidebar hover or before the module check of the page answers.
export function prefetchStore(client: QueryClient, prefix: string) {
  void client.prefetchQuery(productsQuery(prefix));
  void client.prefetchQuery(ordersQuery(prefix));
}

// The products and orders of the org store.
export function useStore(prefix: string) {
  const products = useQuery(productsQuery(prefix));
  const orders = useQuery(ordersQuery(prefix));
  return { products, orders };
}
