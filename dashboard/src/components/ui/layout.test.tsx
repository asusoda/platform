// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EmptyState, PageError } from './feedback';
import { PageHeader, PageMetaProvider } from './layout';

afterEach(cleanup);

const meta = { label: 'Points', description: 'Members and their points.', docs: 'modules/points' };

describe('PageHeader', () => {
  it('takes the title, description and docs link from the page registry', () => {
    render(
      <PageMetaProvider value={meta}>
        <PageHeader />
      </PageMetaProvider>,
    );
    expect(screen.getByRole('heading', { name: 'Points' })).toBeTruthy();
    expect(screen.getByText('Members and their points.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Docs' }).getAttribute('href')).toMatch(/\/docs\/modules\/points$/);
  });

  it('uses its own title with no registry description, and keeps the docs link', () => {
    render(
      <PageMetaProvider value={meta}>
        <PageHeader title="club/faq" />
      </PageMetaProvider>,
    );
    expect(screen.getByRole('heading', { name: 'club/faq' })).toBeTruthy();
    expect(screen.queryByText('Members and their points.')).toBeNull();
    expect(screen.getByRole('link', { name: 'Docs' })).toBeTruthy();
  });

  it('shows the description the page passes', () => {
    render(
      <PageMetaProvider value={meta}>
        <PageHeader description="Updated 2m ago." />
      </PageMetaProvider>,
    );
    expect(screen.getByRole('heading', { name: 'Points' })).toBeTruthy();
    expect(screen.getByText('Updated 2m ago.')).toBeTruthy();
  });
});

describe('EmptyState', () => {
  it('adds a docs link next to the action', () => {
    render(<EmptyState title="No feeds yet" docs="modules/feeds" action={<button type="button">New feed</button>} />);
    expect(screen.getByRole('button', { name: 'New feed' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Docs' }).getAttribute('href')).toMatch(/\/docs\/modules\/feeds$/);
  });
});

describe('PageError', () => {
  it('shows the error and tries again', async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(<PageError error={new Error('The API is down')} retry={retry} />);
    expect(screen.getByRole('alert').textContent).toBe('The API is down');
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
