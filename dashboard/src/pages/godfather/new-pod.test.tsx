// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { GpuType } from '../../lib/types';
import { gpuLabel, NewPodDialog } from './new-pod';

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

const GPUS: GpuType[] = [
  { id: 'NVIDIA RTX A4500', name: 'RTX A4500', memory: 20, price: 0.19, availability: 'LOW' },
  { id: 'NVIDIA RTX A4000', name: 'RTX A4000', memory: 16, price: 0.17, availability: 'NONE' },
];

// Answers the routes the dialog reads, and records the pod create body.
function stubApi(created: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
      if (url.includes('/hosting/providers')) return json({ providers: [{ name: 'runpod', title: 'RunPod', configured: true, godfather: true }] });
      if (url.includes('/gpu-types')) return json({ gpu_types: GPUS });
      if (url.endsWith('/pods') && init?.method === 'POST') {
        created.push(JSON.parse(String(init.body)));
        return json({ pod: {} });
      }
      return json({ settings: { pod_image: null, deployment_pod_image: 'ghcr.io/theaisocietyasu/godfather-base:latest' } });
    }),
  );
}

describe('new pod GPU picker', () => {
  it('labels a GPU with memory, price and stock', () => {
    expect(gpuLabel(GPUS[0])).toBe('RTX A4500 · 20 GB · $0.19/hr · low stock');
  });

  it('lists RunPod stock, blocks GPUs with none free and creates on one in stock', async () => {
    const created: unknown[] = [];
    stubApi(created);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <NewPodDialog prefix="ais" onClose={() => {}} />
      </QueryClientProvider>,
    );
    const select = (await screen.findByRole('combobox', { name: 'GPU type' })) as HTMLSelectElement;
    const none = screen.getByRole('option', { name: /RTX A4000/ }) as HTMLOptionElement;
    expect(none.disabled).toBe(true);
    await waitFor(() => expect(select.value).toBe('NVIDIA RTX A4500'));
    expect(screen.getByText('1 of 2 types in stock on this cloud now')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Create pod' }));
    await waitFor(() => expect(created).toHaveLength(1));
    expect((created[0] as { gpu_type_id: string }).gpu_type_id).toBe('NVIDIA RTX A4500');
    expect(created[0]).not.toHaveProperty('member_setup');
  });
});
