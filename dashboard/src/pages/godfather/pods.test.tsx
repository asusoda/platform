// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ConfirmProvider } from '../../components/confirm';
import type { Pod } from '../../lib/types';
import { PodsTable } from './pods';

// jsdom has no modal dialogs. The stand-ins open and close the dialog element.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const pod = (overrides: Partial<Pod>): Pod => ({
  id: 'pod1',
  name: 'workshop',
  provider: 'runpod',
  status: 'RUNNING',
  is_public: true,
  allowed_users: [],
  created_by: '1',
  created_at: null,
  machine: null,
  cost_per_hour: null,
  image: 'ghcr.io/theaisocietyasu/godfather-base:latest',
  image_version: '2.3.0',
  image_current: true,
  admin_enabled: false,
  admin_enabled_by: null,
  owner: '1',
  can_change_admin: true,
  ...overrides,
});

function show(pods: Pod[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <PodsTable prefix="soda" pods={pods} open={() => {}} />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

describe('pods table', () => {
  it('flags a pod on an old image and recreates it after the data loss warning', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    show([pod({ image_version: null, image_current: false })]);

    expect(screen.getByText('Old image')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Recreate' }));
    expect(await screen.findByText(/members lose every file on it/)).toBeTruthy();
    await user.click(await screen.findByRole('button', { name: 'Recreate' }));
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/compute\/soda\/pods\/pod1\/action$/),
        expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'recreate' }) }),
      ),
    );
  });

  it('shows no old image flag for a current pod and marks pod admin', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
    show([pod({ admin_enabled: true })]);
    expect(screen.queryByText('Old image')).toBeNull();
    expect(screen.getByText('Pod admin')).toBeTruthy();
  });
});
