// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './app';
import { ConfirmProvider } from './components/confirm';
import { TooltipProvider } from './components/tooltip';
import { tokens } from './lib/auth';

const SODA = { id: 1, name: 'SoDA', prefix: 'soda', guild_id: '1', icon_url: null };
const AIS = { id: 2, name: 'AIS', prefix: 'ais', guild_id: '2', icon_url: null };

let calls: string[] = [];

// Answers each API path from the table, 404 for any other path, and keeps the paths it was asked for.
function serve(table: Record<string, unknown>) {
  calls = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL) => {
      const path = new URL(String(input), 'http://api.test').pathname;
      calls.push(path);
      if (path === '/api/superadmin/check') {
        const yes = table[path] === true;
        return new Response(JSON.stringify({ is_superadmin: yes }), { status: yes ? 200 : 403 });
      }
      return path in table
        ? new Response(JSON.stringify(table[path]), { status: 200 })
        : new Response(JSON.stringify({ error: 'not found' }), { status: 404 });
    }),
  );
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>;
}

function open(path: string) {
  render(
    <TooltipProvider>
      <ConfirmProvider>
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <MemoryRouter initialEntries={[path]}>
            <App />
            <Where />
          </MemoryRouter>
        </QueryClientProvider>
      </ConfirmProvider>
    </TooltipProvider>,
  );
}

const superadminData = {
  '/api/superadmin/check': true,
  '/api/organizations/': [SODA, AIS],
  '/api/superadmin/orgs': { orgs: [] },
  '/api/superadmin/audit': { entries: [] },
};

// jsdom has no ResizeObserver. The tabs of some org pages use it.
class NoResize {
  observe() {}
  disconnect() {}
}

beforeEach(() => {
  tokens.set('test-token');
  vi.stubGlobal('ResizeObserver', NoResize);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  tokens.clear();
});

describe('superadmin space', () => {
  it('moves the old org path to /admin', async () => {
    serve(superadminData);
    open('/soda/admin');
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeTruthy();
    expect(screen.getByTestId('where').textContent).toBe('/admin');
  });

  it('shows the superadmin pages in their own sidebar', async () => {
    serve(superadminData);
    open('/admin/errors');
    expect(await screen.findByRole('heading', { name: 'Errors' })).toBeTruthy();
    const sidebar = screen.getByRole('complementary', { name: 'Sidebar' });
    expect(within(sidebar).getByRole('link', { name: 'Organizations' }).getAttribute('href')).toBe('/admin/orgs');
    expect(await within(sidebar).findByRole('option', { name: 'SoDA' })).toBeTruthy();
  });

  it('shows not allowed to an officer and reads no superadmin data', async () => {
    serve({ '/api/superadmin/check': false, '/api/organizations/': [SODA] });
    open('/admin/orgs');
    expect(await screen.findByRole('heading', { name: 'Not allowed' })).toBeTruthy();
    expect(calls.filter((c) => c.startsWith('/api/superadmin/'))).toEqual(['/api/superadmin/check']);
    expect(screen.queryByRole('complementary', { name: 'Sidebar' })).toBeNull();
  });
});

describe('superadmin entry points', () => {
  it('offers Superadmin in the org switcher and the top bar only to the superadmin', async () => {
    serve({ '/api/superadmin/check': true, '/api/organizations/': [SODA] });
    open('/soda/activity');
    expect(await screen.findByRole('link', { name: 'Superadmin' })).toBeTruthy();
    const sidebar = screen.getByRole('complementary', { name: 'Sidebar' });
    expect(await within(sidebar).findByRole('option', { name: 'Superadmin' })).toBeTruthy();
    cleanup();

    serve({ '/api/superadmin/check': false, '/api/organizations/': [SODA] });
    open('/soda/activity');
    const officerSidebar = await screen.findByRole('complementary', { name: 'Sidebar' });
    await within(officerSidebar).findByRole('option', { name: 'SoDA' });
    expect(within(officerSidebar).queryByRole('option', { name: 'Superadmin' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Superadmin' })).toBeNull();
  });

  it('keeps the org list open for the superadmin with one org, with the Superadmin entry', async () => {
    serve({ '/api/superadmin/check': true, '/api/organizations/': [SODA] });
    open('/');
    const entry = await screen.findByRole('link', { name: /Superadmin/ });
    expect(entry.getAttribute('href')).toBe('/admin');
    expect(screen.getByRole('link', { name: /SoDA/ })).toBeTruthy();
    expect(screen.getByTestId('where').textContent).toBe('/');
  });

  it('opens the only org of an officer', async () => {
    serve({ '/api/superadmin/check': false, '/api/organizations/': [SODA] });
    open('/');
    await vi.waitFor(() => expect(screen.getByTestId('where').textContent).toBe('/soda'));
    expect(screen.queryByRole('link', { name: /Superadmin/ })).toBeNull();
  });
});
