// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { ConfirmProvider, DeleteButton } from '../confirm';
import { buttonClass, IconButton, LinkButton, Segmented, TextButton } from './controls';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('DeleteButton', () => {
  it('asks in a dialog before it deletes', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <ConfirmProvider>
        <DeleteButton label="Delete item" question="Delete this item?" onDelete={onDelete} />
      </ConfirmProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Delete item' }));

    const dialog = screen.getByRole('alertdialog');
    expect(dialog.textContent).toContain('Delete this item?');
    expect(onDelete).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it('leaves the row when the officer cancels', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <ConfirmProvider>
        <DeleteButton label="Delete item" question="Delete this item?" onDelete={onDelete} />
      </ConfirmProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Delete item' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });
});

describe('IconButton', () => {
  it('names the button with its label', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <IconButton label="Remove alice" onClick={onClick}>
        <span aria-hidden>x</span>
      </IconButton>,
    );
    await user.click(screen.getByRole('button', { name: 'Remove alice' }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe('LinkButton', () => {
  it('is a link with the button classes', () => {
    render(
      <MemoryRouter>
        <LinkButton to="/soda/explore" variant="primary">
          Open Explore
        </LinkButton>
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: 'Open Explore' });
    expect(link.getAttribute('href')).toBe('/soda/explore');
    expect(link.className).toBe(buttonClass('primary'));
  });
});

describe('TextButton', () => {
  it('is a plain button that does not submit a form', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: { preventDefault: () => void }) => e.preventDefault());
    const onClick = vi.fn();
    render(
      <form onSubmit={onSubmit}>
        <TextButton onClick={onClick}>Clear</TextButton>
      </form>,
    );
    await user.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe('Segmented', () => {
  it('presses the chosen option and reports a new choice', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Segmented
        label="Range"
        value={30}
        onChange={onChange}
        options={[
          { value: 7, label: '7d' },
          { value: 30, label: '30d' },
        ]}
      />,
    );
    const group = screen.getByRole('group', { name: 'Range' });
    expect(group.querySelector('[aria-pressed="true"]')?.textContent).toBe('30d');
    await user.click(screen.getByRole('button', { name: '7d' }));
    expect(onChange).toHaveBeenCalledWith(7);
  });
});
