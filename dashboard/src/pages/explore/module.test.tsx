// @vitest-environment jsdom
import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { tokens } from '../../lib/auth';
import type { CatalogModule } from '../../lib/types';
import { openApp, requests, serve, SODA, stubBrowser } from '../../test/app';

const uptime: CatalogModule = {
  name: 'uptime',
  title: 'Uptime',
  description: 'Checks sites.',
  category: 'Automations',
  parent: null,
  switchable: true,
  enabled: true,
  ready: true,
  needs: [],
  submodules: [],
  shared_content: [],
  limits: [{ key: 'uptime.monitors', label: 'Uptime monitors', window: null, paid_by: 'org' }],
};

const calendar: CatalogModule = {
  ...uptime,
  name: 'calendar',
  title: 'Calendar sync',
  description: 'Copies Notion events.',
  enabled: false,
  ready: false,
  limits: [],
  needs: [{ key: 'notion', label: 'Notion', kind: 'integration', optional: false, connected: false }],
};

const limitRow = {
  key: 'uptime.monitors',
  module: 'uptime',
  label: 'Uptime monitors',
  unit: 'monitors',
  window: null,
  default: 50,
  paid_by: 'org',
  integrations: [],
  value: 50,
  override: false,
  used: 8,
  enabled: true,
};

const table = {
  '/api/organizations/': [SODA],
  '/api/organizations/1/modules': { modules: [] },
  '/api/dashboard/soda/modules': { categories: ['Automations'], modules: [uptime, calendar], layers: [] },
  '/api/organizations/1/limits': { limits: [limitRow] },
  '/api/dashboard/soda/tool-groups': { allowed: null, groups: [{ key: 'uptime', layer: 'module', tools: 4 }] },
  '/api/dashboard/soda/notifications': {
    open: 1,
    notifications: [
      { id: 'event-1', module: 'uptime', subject: 'Website down', message: 'Status 503', link: 'uptime', kind: 'event', level: 'error', at: '2026-11-28T10:00:00Z', resolved_at: null, resolved_by: null },
      { id: 'event-2', module: 'points', subject: 'Other module', message: 'x', link: '', kind: 'event', level: 'info', at: '2026-11-28T09:00:00Z', resolved_at: null, resolved_by: null },
    ],
  },
  'PUT /api/organizations/1/modules': { modules: [] },
};

beforeEach(() => {
  tokens.set('test-token');
  stubBrowser();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  tokens.clear();
});

describe('module page', () => {
  it('shows the module, its limits, tools and its own recent activity', async () => {
    serve(table);
    openApp('/soda/explore/uptime');
    expect(await screen.findByRole('heading', { name: 'Uptime' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Docs' }).getAttribute('href')).toMatch(/\/docs\/modules\/uptime$/);
    expect(screen.getByRole('link', { name: 'Open' }).getAttribute('href')).toBe('/soda/uptime');
    expect(await screen.findByText('8 of 50 monitors')).toBeTruthy();
    expect(await screen.findByText('4 tools for agents and tokens')).toBeTruthy();
    expect(await screen.findByText('Website down')).toBeTruthy();
    expect(screen.queryByText('Other module')).toBeNull();
  });

  it('asks before it turns a module off', async () => {
    const user = userEvent.setup();
    serve(table);
    openApp('/soda/explore/uptime');
    await user.click(await screen.findByRole('switch', { name: 'Uptime on' }));
    const dialog = await screen.findByRole('dialog');
    expect(requests).not.toContain('PUT /api/organizations/1/modules');
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));
    await vi.waitFor(() => expect(requests).toContain('PUT /api/organizations/1/modules'));
  });

  it('links a missing integration to Integrations and hides empty sections', async () => {
    serve(table);
    openApp('/soda/explore/calendar');
    const connect = await screen.findByRole('link', { name: 'Connect' });
    expect(connect.getAttribute('href')).toBe('/soda/explore?tab=integrations');
    expect((screen.getByRole('switch', { name: 'Calendar sync on' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('heading', { name: 'Limits' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Recent activity' })).toBeNull();
  });

  it('says when no module has the name', async () => {
    serve(table);
    openApp('/soda/explore/nope');
    expect(await screen.findByText('No such module')).toBeTruthy();
  });
});
