// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { PointsImport } from '../../lib/types';
import { UploadDialog } from './upload';

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

const run = (over: Partial<PointsImport>): PointsImport => ({
  id: 7,
  event: 'Build night',
  points: 5,
  status: 'running',
  rows_total: 3,
  rows_done: 1,
  awarded: 1,
  skipped: 0,
  errors: [],
  created_by: 'officer',
  created_at: null,
  finished_at: null,
  ...over,
});

describe('CSV upload', () => {
  it('polls the run until it is done, then shows the counts and each failed row', async () => {
    const user = userEvent.setup();
    const answers = [
      run({}),
      run({ status: 'done', rows_done: 3, awarded: 2, errors: [{ row: 4, email: null, message: 'The row has no email or no name' }] }),
    ];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
      if (url.endsWith('/uploadEventCSV') && init?.method === 'POST') return json({ message: 'File is being processed in the background.', import_id: 7 }, 202);
      if (url.endsWith('/imports/7')) return json(answers.length > 1 ? answers.shift() : answers[0]);
      return json({});
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <UploadDialog prefix="soda" open onClose={() => {}} />
      </QueryClientProvider>,
    );

    await user.upload(screen.getByLabelText(/^CSV file/), new File(['Email\n'], 'gbm.csv', { type: 'text/csv' }));
    await user.type(screen.getByLabelText('Event'), 'Build night');
    await user.type(screen.getByLabelText(/^Points for each member/), '5');
    // jsdom counts a required file input with a file as empty, so the test submits the form itself
    fireEvent.submit(screen.getByRole('button', { name: 'Upload' }).closest('form') as HTMLFormElement);

    expect((await screen.findByText('1 of 3 rows')).textContent).toBe('1 of 3 rows');
    expect(screen.getByRole('button', { name: 'Close, keep importing' })).toBeTruthy();
    expect(await screen.findByText(/Import done\. 2 awarded, 0 duplicate rows skipped, 1 failed\./, {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByRole('cell', { name: 'The row has no email or no name' })).toBeTruthy();
    expect(screen.getByRole('cell', { name: '4' })).toBeTruthy();
    expect(screen.queryByText(/Reload this page/)).toBeNull();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/imports/7')).length).toBeGreaterThanOrEqual(2);
  });
});
