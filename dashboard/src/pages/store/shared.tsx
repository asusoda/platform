import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { Order, Product } from '../../lib/types';

// The products and orders of the org store.
export function useStore(prefix: string) {
  const products = useQuery({
    queryKey: ['store', prefix, 'products'],
    queryFn: () => api<Product[]>(`/api/storefront/${prefix}/products`),
  });
  const orders = useQuery({
    queryKey: ['store', prefix, 'orders'],
    queryFn: () => api<Order[]>(`/api/storefront/${prefix}/orders`),
  });
  return { products, orders };
}
