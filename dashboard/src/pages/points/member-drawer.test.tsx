// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ConfirmProvider } from '../../components/confirm';
import type { PointsMember } from '../../lib/types';
import { MemberDrawer } from './member-drawer';

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

const member: PointsMember = {
  id: 1,
  uuid: 'u-1',
  name: 'Alice',
  username: 'alice',
  email: 'alice@asu.edu',
  asu_id: null,
  academic_standing: null,
  major: null,
  discord_linked: false,
  points: 15,
  joined_at: null,
  created_at: null,
};

const entry = (id: number, points: number, event = 'GBM', timestamp: string | null = null) => ({
  id,
  points,
  event,
  awarded_by_officer: 'officer',
  timestamp,
  last_updated: null,
});

const history = { user: { id: 1, name: 'Alice', email: 'alice@asu.edu', username: 'alice' }, total_points: 15, points_history: [entry(11, 5), entry(12, 10)] };

function renderDrawer(body: unknown) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'DELETE') return new Response(JSON.stringify({ message: 'Points deleted successfully' }), { status: 200 });
    if (url.endsWith('/points')) return new Response(JSON.stringify(body), { status: 200 });
    return new Response('{}', { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = (m: PointsMember) => (
    <QueryClientProvider client={client}>
      <ConfirmProvider>
        <MemberDrawer prefix="soda" member={m} onClose={() => {}} onEdit={() => {}} onAward={() => {}} />
      </ConfirmProvider>
    </QueryClientProvider>
  );
  const result = render(view(member));
  return { fetchMock, rerender: (m: PointsMember) => result.rerender(view(m)) };
}

describe('member drawer', () => {
  it('groups entries by event, and a store order with its refund is one line with no delete', async () => {
    renderDrawer({
      ...history,
      points_history: [
        entry(11, 5, 'GBM', '2026-10-01T10:00:00'),
        entry(12, 10, 'GBM', '2026-10-08T10:00:00'),
        entry(13, -40, 'Storefront Purchase - Order #41', '2026-10-09T10:00:00'),
        entry(14, 40, 'Refund - Order #41', '2026-10-10T10:00:00'),
        entry(15, -20, 'Storefront Purchase - Order #42', '2026-10-11T10:00:00'),
      ],
    });
    const groups = await screen.findAllByRole('listitem');
    const lines = groups.filter((li) => li.parentElement?.closest('section') && li.querySelector('ul'));
    expect(lines.map((li) => li.firstElementChild?.textContent)).toEqual(['Order #42held-20', 'Order #41refunded0', 'GBM+15']);
    expect(screen.getAllByRole('button', { name: 'Delete the entry for GBM' })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Order #4/ })).toBeNull();
  });

  it('shows the total of the member it gets, so a new total shows without a refetch', async () => {
    const { fetchMock, rerender } = renderDrawer(history);
    expect((await screen.findByLabelText('Total points')).textContent).toBe('15');
    const calls = fetchMock.mock.calls.length;
    rerender({ ...member, points: 25 });
    expect(screen.getByLabelText('Total points').textContent).toBe('25');
    expect(fetchMock.mock.calls.length).toBe(calls);
  });

  it('deletes the entry the officer clicks by its id, also when two entries share an event name', async () => {
    const user = userEvent.setup();
    const { fetchMock } = renderDrawer(history);

    const buttons = await screen.findAllByRole('button', { name: 'Delete the entry for GBM' });
    expect(buttons).toHaveLength(2);
    await user.click(buttons[1]);
    await user.click(await screen.findByRole('button', { name: 'Delete' }));

    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/api\/points\/soda\/entries\/12$/), expect.objectContaining({ method: 'DELETE' })),
    );
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('delete_points'))).toBe(false);
  });
});
