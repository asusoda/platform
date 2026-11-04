// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { type MemberGodfather, MemberGodfatherPage } from './index';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const body: MemberGodfather = {
  organization: { name: 'AIS', prefix: 'ais' },
  pods: [
    { id: 'pod1', name: 'ml-pod', status: 'RUNNING', is_public: false, image_current: true },
    { id: 'pod2', name: 'old-pod', status: 'EXITED', is_public: true, image_current: false },
  ],
  sessions: [{ pod_id: 'pod1', pod_name: 'ml-pod', title: 'Workshop', start_at: '2026-11-05T18:00:00+00:00', stop_at: '2026-11-05T20:00:00+00:00' }],
  connections: [{ pod_id: 'pod1', pod_name: 'ml-pod', is_admin: false, created_at: '2026-11-03T18:00:00+00:00' }],
  cli: { package: 'godfather-cli', install: 'pip install godfather-cli' },
};

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/godfather/ais']}>
        <Routes>
          <Route path="/godfather/:prefix" element={<MemberGodfatherPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const answer = (json: unknown, status = 200) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(json), { status })));

describe('member Godfather page', () => {
  it('lists the pods, sessions, connections and CLI commands', async () => {
    answer(body);
    renderPage();
    expect(await screen.findByText('old-pod')).toBeTruthy();
    expect(screen.getByText('Old image')).toBeTruthy();
    expect(screen.getByText('Workshop')).toBeTruthy();
    expect(screen.getByText('godfather connect --org ais')).toBeTruthy();
  });

  it('offers Discord sign-in that returns to this page', async () => {
    answer({ error: 'Discord authentication required' }, 401);
    renderPage();
    const link = await screen.findByRole('link', { name: 'Sign in with Discord' });
    expect(link.getAttribute('href')).toMatch(/\/api\/auth\/store_login\?org=ais&page=godfather&client=dashboard$/);
  });
});
