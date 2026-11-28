// Renders the whole dashboard at one path with each API path answered from a table, for page tests.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi } from 'vitest';
import { App } from '../app';
import { ConfirmProvider } from '../components/confirm';
import { TooltipProvider } from '../components/tooltip';

export const SODA = { id: 1, name: 'SoDA', prefix: 'soda', guild_id: '1', icon_url: null };

// The requests the app made, as method and path, such as "PUT /api/organizations/1/modules".
export const requests: string[] = [];

// Answers each API path from the table with 200, and any other path with 404. A function value gets the request
// body and returns the answer.
export function serve(table: Record<string, unknown>) {
  requests.length = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'http://api.test').pathname;
      const method = init?.method ?? 'GET';
      requests.push(`${method} ${path}`);
      if (path === '/api/superadmin/check') return new Response(JSON.stringify({ is_superadmin: false }), { status: 403 });
      const value = table[`${method} ${path}`] ?? table[path];
      if (value === undefined) return new Response(JSON.stringify({ error: 'not found' }), { status: 404 });
      const body = typeof value === 'function' ? value(init?.body ? JSON.parse(String(init.body)) : null) : value;
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

// jsdom has no ResizeObserver. The tabs of some pages use it.
class NoResize {
  observe() {}
  disconnect() {}
}

// Stand-ins for what jsdom lacks: ResizeObserver, and the modal dialog methods.
export function stubBrowser() {
  vi.stubGlobal('ResizeObserver', NoResize);
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
  };
}

export function openApp(path: string) {
  render(
    <TooltipProvider>
      <ConfirmProvider>
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </ConfirmProvider>
    </TooltipProvider>,
  );
}
