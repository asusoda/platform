import { API_URL, ApiError } from '../../lib/api';

// Member requests use the API session cookie, not the officer token.
export async function memberApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: 'include' });
  const text = await response.text();
  let body: { error?: string; message?: string } | null = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) throw new ApiError(body?.error ?? body?.message ?? `Request failed (${response.status})`, response.status);
  return body as T;
}

export type StoreProduct = { id: number; name: string; description: string | null; price: number; stock: number; image_url: string | null };
export type StoreBody = { organization: { name: string; prefix: string; description: string | null }; products: StoreProduct[] };
export type MemberOrder = {
  id: number;
  total_amount: number;
  status: string;
  created_at: string;
  items: { id: number; product_id: number; quantity: number; price_at_time: number; product_name: string }[];
};
export type MemberProfile = { user: { name: string | null; email: string | null }; current_organization: { points: number } };
export type CartLine = { product: StoreProduct; quantity: number };

export const storePath = (prefix: string) => `/store/${encodeURIComponent(prefix)}`;

// Member pages that the API returns to after sign-in, at /<page>/<prefix>.
export type MemberPage = 'store' | 'godfather';

// Starts the member's Discord sign-in. The API returns the browser to the page, with ?error= when it fails.
// The store is the API's default page, so its URL has no page parameter.
export const memberLoginUrl = (prefix: string, page: MemberPage) =>
  `${API_URL}/api/auth/store_login?org=${encodeURIComponent(prefix)}${page === 'store' ? '' : `&page=${page}`}&client=dashboard`;

export const storeLoginUrl = (prefix: string) => memberLoginUrl(prefix, 'store');

// The cart lines with current product details: missing or sold-out products go, quantities stop at stock.
export function freshCart(lines: CartLine[], products: StoreProduct[]): CartLine[] {
  const byId = new Map(products.map((p) => [p.id, p]));
  return lines.flatMap((line) => {
    const product = byId.get(line.product.id);
    const quantity = product ? Math.min(line.quantity, product.stock) : 0;
    return product && quantity > 0 ? [{ product, quantity }] : [];
  });
}
