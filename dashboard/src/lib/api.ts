import { tokens } from './auth';

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function refresh(): Promise<boolean> {
  const refreshToken = tokens.refresh();
  if (!refreshToken) return false;
  const response = await fetch(`${API_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return false;
  const body = (await response.json()) as { access_token: string };
  tokens.set(body.access_token);
  return true;
}

// Sends a request with the access token, refreshing it once on a 401.
async function request(path: string, init: RequestInit, retried = false): Promise<Response> {
  const headers = new Headers(init.headers);
  const access = tokens.access();
  if (access) headers.set('Authorization', `Bearer ${access}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (response.status === 401 && !retried && (await refresh())) return request(path, init, true);
  return response;
}

function failure(response: Response, body: { error?: string; message?: string } | null): ApiError {
  if (response.status === 401) tokens.clear();
  return new ApiError(body?.error ?? body?.message ?? `Request failed (${response.status})`, response.status);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) throw failure(response, body);
  return body as T;
}

// A binary response, such as a file attachment, as a Blob.
export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await request(path, init);
  if (!response.ok) {
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    throw failure(response, body);
  }
  return response.blob();
}

export const send = <T>(path: string, method: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export function loginUrl(): string {
  return `${API_URL}/api/auth/login?client=dashboard`;
}

export async function exchangeLoginCode(code: string): Promise<void> {
  const body = await send<{ access_token: string; refresh_token: string }>('/api/auth/exchange', 'POST', { code });
  tokens.set(body.access_token, body.refresh_token);
}
