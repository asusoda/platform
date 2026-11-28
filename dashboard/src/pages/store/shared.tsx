import { type QueryClient, queryOptions, useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { POINTS_REFETCH_MS } from '../points/shared';
import { compact } from '../../lib/format';
import type { Order, Product } from '../../lib/types';

// Order statuses an officer still has to act on.
export const OPEN = new Set(['pending', 'processing', 'shipped']);

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
    // Member orders arrive from the member store, so the list asks again
    refetchInterval: POINTS_REFETCH_MS,
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

// True for an open order that holds no points: a member order placed before orders held points.
export const holdsNothing = (order: Pick<Order, 'points_held' | 'status'>) => order.points_held <= 0 && OPEN.has(order.status);

// The points an order holds, as the order shows them.
export const heldLabel = (order: Pick<Order, 'points_held' | 'status'>) => (holdsNothing(order) ? 'No points held' : compact(order.points_held));

// The points that orders took, less refunds. Cancelled orders hold none.
export const pointsSpent = (orders: Order[]) => orders.reduce((n, o) => n + (o.status === 'cancelled' ? 0 : o.points_held), 0);
