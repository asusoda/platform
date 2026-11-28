// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Delivery } from '../lib/types';
import { RecentMessages } from './alerts';

afterEach(cleanup);

const delivery = (overrides: Partial<Delivery>): Delivery => ({
  id: 1,
  destination_id: 7,
  source: 'event',
  ref: 'errors',
  title: 'KeyError',
  status: 'sent',
  error: null,
  message_url: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

describe('recent messages', () => {
  it('shows each message with its destination, its error and the link to a bot post', () => {
    render(
      <RecentMessages
        names={new Map([[7, 'Errors']])}
        deliveries={[
          delivery({ id: 3, source: 'leetcode', destination_id: null, title: 'Daily LeetCode: Two Sum', message_url: 'https://discord.com/channels/1/2/3' }),
          delivery({ id: 2, source: 'feed', ref: 'internships', title: 'New Job: Acme', status: 'failed', error: 'Discord refused the message with status 404' }),
          delivery({ id: 1 }),
        ]}
      />,
    );
    expect(screen.getByRole('link', { name: 'Daily LeetCode: Two Sum' }).getAttribute('href')).toBe('https://discord.com/channels/1/2/3');
    expect(screen.getByText('Bot')).toBeTruthy();
    expect(screen.getAllByText('Errors')).toHaveLength(2);
    expect(screen.getByText('Discord refused the message with status 404')).toBeTruthy();
    expect(screen.getByText('Feed')).toBeTruthy();
  });

  it('says when nothing was sent yet', () => {
    render(<RecentMessages names={new Map()} deliveries={[]} />);
    expect(screen.getByText('No messages yet')).toBeTruthy();
  });
});
