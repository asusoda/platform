import { useMutation } from '@tanstack/react-query';
import { Cpu, Gpu, Plus, X } from 'lucide-react';
import { useState } from 'react';
import { Button, cx, Dialog, Field, FormActions, Input, Select, Switch } from '../../components/ui';
import { send } from '../../lib/api';
import type { NewPod } from '../../lib/types';
import { firstConfigured, ProviderField, providerTitle, useProviders } from '../hosting/providers';
import { UsersEditor } from './members';
import { computePath, useComputeSettings, useRefreshCompute } from './shared';

// Defaults and limits match pod_request in modules/compute/service.py.
const DEFAULT_GPU = 'NVIDIA RTX A4000';
const DEFAULT_CPU = 'cpu3c';
const RESERVED_PREFIX = 'GODFATHER_';
const GPUS = [
  'NVIDIA RTX A4000',
  'NVIDIA RTX A5000',
  'NVIDIA RTX A6000',
  'NVIDIA A40',
  'NVIDIA L4',
  'NVIDIA L40S',
  'NVIDIA GeForce RTX 4090',
  'NVIDIA RTX 6000 Ada Generation',
  'NVIDIA A100 80GB PCIe',
  'NVIDIA H100 80GB HBM3',
];
const CPUS = ['cpu3c', 'cpu3g', 'cpu3m', 'cpu5c', 'cpu5g', 'cpu5m'];

type EnvRow = { key: number; name: string; value: string };

type Draft = {
  name: string;
  image: string;
  cpu: boolean;
  gpu: string;
  flavor: string;
  vcpus: string;
  cloud: NewPod['cloud_type'];
  volume: string;
  disk: string;
  mount: string;
  isPublic: boolean;
  users: string[];
};

const EMPTY: Draft = {
  name: '',
  image: '',
  cpu: false,
  gpu: DEFAULT_GPU,
  flavor: DEFAULT_CPU,
  vcpus: '2',
  cloud: 'COMMUNITY',
  volume: '0',
  disk: '20',
  mount: '/workspace',
  isPublic: false,
  users: [],
};

function envProblem(rows: EnvRow[]): string | null {
  const names = rows.map((r) => r.name.trim()).filter(Boolean);
  if (names.some((n) => n.startsWith(RESERVED_PREFIX))) return `Names starting with ${RESERVED_PREFIX} are reserved for the pod image.`;
  if (names.some((n) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(n))) return 'Use letters, digits and underscores, not starting with a digit.';
  if (new Set(names).size !== names.length) return 'Each name can appear once.';
  return null;
}

function Choice({ on, onClick, icon: Icon, title, hint }: { on: boolean; onClick: () => void; icon: typeof Cpu; title: string; hint: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={on}
      onClick={onClick}
      className={cx(
        'flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        on ? 'border-fg/40 bg-panel-2' : 'border-line hover:bg-panel-2/50',
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0 text-muted" />
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{hint}</span>
      </span>
    </button>
  );
}

export function NewPodDialog({ prefix, onClose }: { prefix: string; onClose: () => void }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [env, setEnv] = useState<EnvRow[]>([]);
  const [nextKey, setNextKey] = useState(1);
  const refresh = useRefreshCompute(prefix);
  const defaults = useComputeSettings(prefix);
  const providers = useProviders(prefix);
  const [chosen, setChosen] = useState<string | null>(null);
  const provider = chosen ?? firstConfigured(providers.data);
  const title = providerTitle(providers.data, provider);
  // The hardware, cloud and volume fields follow the RunPod v2 API, so they show for RunPod only
  const runpod = provider === 'runpod';
  const connected = providers.data ? Boolean(providers.data.find((p) => p.name === provider)?.configured) : true;
  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });
  const problem = envProblem(env);
  const create = useMutation({
    mutationFn: () => {
      const body: NewPod = {
        provider,
        use_cpu_only: draft.cpu,
        container_disk_in_gb: Number(draft.disk),
        volume_mount_path: draft.mount.trim() || '/workspace',
        env: Object.fromEntries(env.filter((r) => r.name.trim()).map((r) => [r.name.trim(), r.value])),
        is_public: draft.isPublic,
        allowed_users: draft.users,
      };
      if (runpod) {
        body.cloud_type = draft.cloud;
        body.volume_in_gb = draft.cpu ? 0 : Number(draft.volume);
      }
      if (draft.name.trim()) body.name = draft.name.trim();
      if (draft.image.trim()) body.image_name = draft.image.trim();
      if (!runpod) return send(`${computePath(prefix)}/pods`, 'POST', body);
      if (draft.cpu) {
        body.cpu_flavor = draft.flavor.trim() || DEFAULT_CPU;
        body.vcpu_count = Number(draft.vcpus);
      } else body.gpu_type_id = draft.gpu.trim() || DEFAULT_GPU;
      return send(`${computePath(prefix)}/pods`, 'POST', body);
    },
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  const editEnv = (key: number, patch: Partial<EnvRow>) => setEnv(env.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  return (
    <Dialog open onClose={onClose} wide title="New pod" description="Creates a pod on the org's account at the selected hosting provider. It starts right away.">
      <form
        className="space-y-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (!problem) create.mutate();
        }}
      >
        <ProviderField
          prefix={prefix}
          providers={providers.data}
          value={provider}
          onChange={setChosen}
          hint="The cloud account the pod runs on and bills."
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Name" hint="Leave empty for a random name">
            <Input value={draft.name} onChange={set('name')} placeholder="workshop" maxLength={100} />
          </Field>
          <Field label="Image" hint="Leave empty for the org's default pod image, set in Pod settings">
            <Input
              value={draft.image}
              onChange={set('image')}
              placeholder={defaults.data ? (defaults.data.pod_image ?? defaults.data.deployment_pod_image) : ''}
              className="font-mono text-xs"
            />
          </Field>
        </div>

        {runpod ? (
          <fieldset className="space-y-3">
            <legend className="mb-1.5 text-sm font-medium">Hardware</legend>
            <div role="radiogroup" aria-label="Hardware" className="grid gap-2 sm:grid-cols-2">
              <Choice on={!draft.cpu} onClick={() => setDraft({ ...draft, cpu: false })} icon={Gpu} title="GPU" hint="One GPU, for training and inference" />
              <Choice on={draft.cpu} onClick={() => setDraft({ ...draft, cpu: true })} icon={Cpu} title="CPU only" hint="Cheaper, for labs that need no GPU" />
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              {draft.cpu ? (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="CPU flavor" hint="A RunPod CPU flavor id">
                    <Input value={draft.flavor} onChange={set('flavor')} list="cpu-flavors" className="font-mono text-xs" />
                  </Field>
                  <Field label="vCPUs">
                    <Select value={draft.vcpus} onChange={set('vcpus')}>
                      {['2', '4', '8', '16'].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
              ) : (
                <Field label="GPU type" hint="A RunPod GPU type id">
                  <Input value={draft.gpu} onChange={set('gpu')} list="gpu-types" />
                </Field>
              )}
              <Field label="Cloud" hint="Secure cloud costs more and runs in data centers">
                <Select value={draft.cloud} onChange={set('cloud')}>
                  <option value="COMMUNITY">Community cloud</option>
                  <option value="SECURE">Secure cloud</option>
                </Select>
              </Field>
            </div>
            <datalist id="gpu-types">
              {GPUS.map((g) => (
                <option key={g} value={g} />
              ))}
            </datalist>
            <datalist id="cpu-flavors">
              {CPUS.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </fieldset>
        ) : null}

        <div className="grid gap-5 sm:grid-cols-3">
          {runpod ? (
            <Field label="Volume (GB)" hint={draft.cpu ? 'CPU pods have no volume on RunPod.' : 'Kept when the pod stops. 0, or 10 to 2000'}>
              <Input
                type="number"
                min={0}
                max={2000}
                step={1}
                value={draft.cpu ? '0' : draft.volume}
                onChange={set('volume')}
                disabled={draft.cpu}
                required
              />
            </Field>
          ) : null}
          <Field label="Container disk (GB)" hint="Lost when the pod stops. 1 to 500">
            <Input type="number" min={1} max={500} step={1} value={draft.disk} onChange={set('disk')} required />
          </Field>
          <Field label="Volume mount path">
            <Input value={draft.mount} onChange={set('mount')} className="font-mono text-xs" disabled={draft.cpu} required />
          </Field>
        </div>

        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Environment variables</legend>
          {env.length ? (
            <div className="mb-2 space-y-2">
              {env.map((row) => (
                <div key={row.key} className="flex gap-2">
                  <Input
                    aria-label="Variable name"
                    placeholder="HF_HOME"
                    value={row.name}
                    onChange={(e) => editEnv(row.key, { name: e.target.value })}
                    aria-invalid={row.name.trim().startsWith(RESERVED_PREFIX)}
                    className="font-mono text-xs"
                  />
                  <Input
                    aria-label="Variable value"
                    placeholder="/workspace/hf"
                    value={row.value}
                    onChange={(e) => editEnv(row.key, { value: e.target.value })}
                    className="font-mono text-xs"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove ${row.name || 'variable'}`}
                    onClick={() => setEnv(env.filter((r) => r.key !== row.key))}
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : null}
          <Button
            type="button"
            onClick={() => {
              setEnv([...env, { key: nextKey, name: '', value: '' }]);
              setNextKey(nextKey + 1);
            }}
          >
            <Plus className="size-4" /> Add variable
          </Button>
          <p className={cx('mt-1.5 text-xs', problem ? 'text-bad' : 'text-muted')}>
            {problem ?? `Values are passed to the pod as is. Names starting with ${RESERVED_PREFIX} are reserved.`}
          </p>
        </fieldset>

        <div className="space-y-4 border-t border-line pt-5">
          <div className="flex items-start justify-between gap-4 rounded-lg border border-line p-3">
            <div>
              <div className="text-sm font-medium">Open to all members</div>
              <div className="mt-0.5 text-xs text-muted">Every member of the Discord server can connect while it runs.</div>
            </div>
            <Switch checked={draft.isPublic} onChange={(v) => setDraft({ ...draft, isPublic: v })} label="Open to all members" />
          </div>
          <UsersEditor prefix={prefix} users={draft.users} onChange={(users) => setDraft({ ...draft, users })} />
        </div>

        <p className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-xs text-pretty">
          {title} bills the org's account by the hour while the pod runs, at the price of the hardware and cloud
          you pick. A stopped pod still costs its volume. Stop or terminate pods you do not use, or add sessions so the
          schedule stops them.
        </p>

        <FormActions error={create.error}>
          <Button variant="primary" disabled={create.isPending || Boolean(problem) || !connected}>
            {create.isPending ? 'Creating...' : 'Create pod'}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}
