import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Boxes, ChevronRight, ExternalLink, GitBranch, History, Pencil, Plus, RefreshCw, Rocket, Trash2, X } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Code,
  cx,
  Dialog,
  Dot,
  EmptyState,
  ErrorNote,
  Field,
  FormActions,
  Input,
  Mono,
  PageHeader,
  SkeletonRows,
  Spinner,
  Table,
  Td,
  Textarea,
  Th,
  Tr,
} from '../components/ui';
import { api, send } from '../lib/api';
import { deployTone, duration, podTone, timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import type { App, AppDetail, AppKind, AppManifest, DeployPreview, RunPodPod } from '../lib/types';

const DEFAULT_MANIFEST_PATH = 'platform.app.yaml';
const NAME_PATTERN = /^[a-z0-9][a-z0-9-]{0,62}$/;
const TAG_PATTERN = /^([A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|sha256:[a-f0-9]{64})$/;
const REPO_PATTERN = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/;

const EXAMPLE_MANIFEST = {
  kind: 'bot',
  description: 'The club Discord bot',
  image: 'ghcr.io/example-club/club-bot',
  gpu: { id: 'NVIDIA RTX A5000', count: 1 },
  cloud: 'SECURE',
  disk: 50,
  ports: ['8080/http'],
  env: { MODE: 'prod' },
  secret_env: { DISCORD_TOKEN: 'app_club_bot_discord_token' },
  health: { port: 8080, path: '/health' },
};

// Apps are grouped by what they are for; the host is a detail of each app.
const KINDS: { kind: AppKind; title: string; hint: string }[] = [
  { kind: 'bot', title: 'Bots', hint: 'Discord and chat bots' },
  { kind: 'agent', title: 'Agents', hint: 'AI agents that call the platform with a token' },
  { kind: 'site', title: 'Sites', hint: 'Websites and web apps' },
  { kind: 'service', title: 'Services', hint: 'APIs, workers and anything else' },
];
const HOSTS: Record<App['host'], string> = { runpod: 'RunPod' };

const pretty = (value: unknown) => JSON.stringify(value, null, 2);

// officer:<discord id> reads as officer; tokens keep their name.
const actorLabel = (actor: string | null) => (actor ? actor.replace(/^officer:\d+$/, 'officer') : '-');

// Parses manifest JSON and checks the fields the server requires. The server checks the full schema.
function readManifest(text: string): { manifest?: AppManifest; error?: string } {
  if (!text.trim()) return { error: 'Paste a manifest' };
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (e) {
    return { error: `Not valid JSON: ${e instanceof Error ? e.message : String(e)}` };
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { error: 'The manifest must be a JSON object' };
  const m = value as AppManifest;
  if (typeof m.image !== 'string') return { error: 'image is required, without a tag' };
  if (/:[^/]*$/.test(m.image) || m.image.includes('@')) return { error: 'image has no tag; the deploy gives the tag' };
  if (!m.health || typeof m.health !== 'object') return { error: 'health is required: {"port": 8080, "path": "/health"}' };
  if (('gpu' in m) === ('cpu' in m)) return { error: 'Give gpu or cpu, not both' };
  return { manifest: m };
}

function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre
      className={cx(
        'max-h-80 overflow-auto rounded-lg border border-line bg-panel-2/50 p-3 font-mono text-xs leading-relaxed',
        className,
      )}
    >
      {pretty(value)}
    </pre>
  );
}

function Label({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 flex min-h-8 items-center justify-between gap-2">
      <h3 className="font-mono text-[11px] tracking-wider text-muted uppercase">{children}</h3>
      {action}
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 truncate text-sm">{children}</div>
    </div>
  );
}

function useInvalidate(prefix: string) {
  const client = useQueryClient();
  return (name?: string) => {
    client.invalidateQueries({ queryKey: ['apps', prefix] });
    client.invalidateQueries({ queryKey: ['overview', prefix] });
    if (name) client.invalidateQueries({ queryKey: ['app', prefix, name] });
  };
}

// Registering

type Source = 'repo' | 'inline';

function SourceChoice({ value, onChange }: { value: Source; onChange: (v: Source) => void }) {
  const options: { id: Source; title: string; text: string }[] = [
    { id: 'repo', title: 'From repository', text: 'Read platform.app.yaml at each deploy, reviewed like code.' },
    { id: 'inline', title: 'Inline manifest', text: 'Keep the manifest here and edit it in the dashboard.' },
  ];
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium">Manifest source</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((o) => (
          <label
            key={o.id}
            className={cx(
              'flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring',
              value === o.id ? 'border-fg/40 bg-panel-2' : 'border-line hover:bg-panel-2/50',
            )}
          >
            <input
              type="radio"
              name="manifest-source"
              className="mt-0.5 size-4 accent-current"
              checked={value === o.id}
              onChange={() => onChange(o.id)}
            />
            <span className="min-w-0">
              <span className="block font-medium">{o.title}</span>
              <span className="mt-0.5 block text-xs text-muted">{o.text}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function ManifestInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const check = value.trim() ? readManifest(value) : {};
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor="manifest-json" className="text-sm font-medium">
          Manifest (JSON)
        </label>
        <button type="button" className="rounded-sm text-xs text-muted transition-colors hover:text-fg" onClick={() => onChange(pretty(EXAMPLE_MANIFEST))}>
          Insert example
        </button>
      </div>
      <Textarea
        id="manifest-json"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        rows={14}
        className="font-mono text-xs leading-relaxed"
        placeholder={pretty({ image: 'ghcr.io/org/app', cpu: { id: 'cpu5c', vcpuCount: 4 }, health: { port: 8080, path: '/health' } })}
        aria-invalid={Boolean(check.error)}
        aria-describedby="manifest-hint"
      />
      <span id="manifest-hint" className={cx('block text-xs', check.error ? 'text-bad' : 'text-muted')}>
        {check.error ??
          'Required: image (no tag), gpu or cpu, and health. secret_env maps a pod env var to an org secret named app_...'}
      </span>
    </div>
  );
}

function RegisterApp({ prefix, onDone }: { prefix: string; onDone: (name: string | null) => void }) {
  const invalidate = useInvalidate(prefix);
  const [name, setName] = useState('');
  const [source, setSource] = useState<Source>('repo');
  const [repo, setRepo] = useState('');
  const [path, setPath] = useState(DEFAULT_MANIFEST_PATH);
  const [text, setText] = useState('');
  const nameOk = !name || NAME_PATTERN.test(name);
  const repoOk = !repo || REPO_PATTERN.test(repo);
  const parsed = readManifest(text);
  const ready = NAME_PATTERN.test(name) && (source === 'repo' ? REPO_PATTERN.test(repo) && path.trim() : parsed.manifest);
  const create = useMutation({
    mutationFn: () =>
      send<App>(
        `/api/dashboard/${prefix}/apps/${name}`,
        'PUT',
        source === 'repo' ? { repo, manifest_path: path.trim() || DEFAULT_MANIFEST_PATH } : { manifest: parsed.manifest },
      ),
    onSuccess: () => {
      invalidate(name);
      onDone(name);
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) create.mutate();
      }}
    >
      <Field label="Name" hint={
          nameOk
            ? `Lowercase letters, digits and dashes. The pod is named ${prefix}-${name || '<name>'}.`
            : 'Use lowercase letters, digits and dashes, starting with a letter or digit.'
        }>
        <Input value={name} onChange={(e) => setName(e.target.value.trim())} placeholder="club-bot" aria-invalid={!nameOk} required autoFocus />
      </Field>
      <SourceChoice value={source} onChange={setSource} />
      {source === 'repo' ? (
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Repository" hint={repoOk ? 'owner/name. Private repos need the org secret github_token.' : 'Use the form owner/name.'}>
            <Input value={repo} onChange={(e) => setRepo(e.target.value.trim())} placeholder="example-club/club-bot" aria-invalid={!repoOk} required />
          </Field>
          <Field label="Manifest path" hint="Read from the default branch now, and at the git ref of each deploy.">
            <Input value={path} onChange={(e) => setPath(e.target.value)} className="font-mono" required />
          </Field>
        </div>
      ) : (
        <ManifestInput value={text} onChange={setText} />
      )}
      <FormActions error={create.error}>
        <Button variant="primary" disabled={!ready || create.isPending}>
          {create.isPending ? <Spinner className="size-3.5" /> : null}
          Register app
        </Button>
        <Button type="button" variant="ghost" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

// Detail panels

function PodStatus({ prefix, app }: { prefix: string; app: App }) {
  const pod = useQuery({
    queryKey: ['app-pod', prefix, app.name],
    queryFn: () => api<{ pod: RunPodPod | null }>(`/api/dashboard/${prefix}/apps/${app.name}/pod`),
    enabled: Boolean(app.pod_id),
    retry: false,
    refetchInterval: 30_000,
  });
  if (!app.pod_id) {
    return <p className="text-sm text-muted">No pod yet. The first deploy creates it.</p>;
  }
  if (pod.isLoading) return <SkeletonRows rows={1} />;
  if (pod.error) return <ErrorNote error={pod.error} />;
  const p = pod.data?.pod;
  if (!p) {
    return (
      <p className="text-sm text-muted">
        RunPod has no pod <Mono>{app.pod_id}</Mono>. It was terminated; the next deploy creates a new one.
      </p>
    );
  }
  const status = p.desiredStatus ?? 'UNKNOWN';
  const machine = p.gpu?.displayName
    ? `${p.gpu.count && p.gpu.count > 1 ? `${p.gpu.count} x ` : ''}${p.gpu.displayName}`
    : (p.machine?.gpuDisplayName ?? p.machine?.cpuTypeId ?? null);
  const cost = p.costPerHr !== undefined && p.costPerHr !== null ? Number(p.costPerHr) : null;
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Fact label="Status">
        <span className="inline-flex items-center gap-2">
          <Dot tone={podTone(status)} />
          {status.toLowerCase()}
        </span>
      </Fact>
      <Fact label="Machine">{machine ?? '-'}</Fact>
      <Fact label="Cost">{cost !== null && Number.isFinite(cost) ? `$${cost.toFixed(2)}/hr` : '-'}</Fact>
      <Fact label="Pod ID">
        <Mono className="text-fg">{app.pod_id}</Mono>
      </Fact>
      {p.image ? (
        <div className="col-span-2 sm:col-span-4">
          <Fact label="Image">
            <Mono className="text-fg" title={p.image}>
              {p.image}
            </Mono>
          </Fact>
        </div>
      ) : null}
    </div>
  );
}

function DeployPanel({ prefix, app, onDone }: { prefix: string; app: App; onDone: () => void }) {
  const invalidate = useInvalidate(prefix);
  const [tag, setTag] = useState('');
  const [ref, setRef] = useState('');
  const tagOk = !tag || TAG_PATTERN.test(tag);
  const body = (dryRun: boolean) => ({ tag, ...(app.repo && ref.trim() ? { ref: ref.trim() } : {}), dry_run: dryRun });
  const preview = useMutation({
    mutationFn: () => send<DeployPreview>(`/api/dashboard/${prefix}/apps/${app.name}/deploy`, 'POST', body(true)),
  });
  const deploy = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/apps/${app.name}/deploy`, 'POST', body(false)),
    onSuccess: () => {
      invalidate(app.name);
      onDone();
    },
  });
  const edit = (set: (v: string) => void) => (e: { target: { value: string } }) => {
    set(e.target.value.trim());
    preview.reset();
  };
  return (
    <form
      className="space-y-4 rounded-lg border border-line p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (preview.isSuccess) deploy.mutate();
        else if (TAG_PATTERN.test(tag)) preview.mutate();
      }}
    >
      <div className={cx('grid gap-4', app.repo && 'sm:grid-cols-2')}>
        <Field label="Image tag" hint={tagOk ? 'A tag such as v1.2.0, or a sha256 digest.' : 'Not a valid tag or sha256 digest.'}>
          <Input value={tag} onChange={edit(setTag)} placeholder="v1.2.0" className="font-mono" aria-invalid={!tagOk} required autoFocus />
        </Field>
        {app.repo ? (
          <Field label="Git ref (optional)" hint={`The commit or branch to read ${app.manifest_path ?? DEFAULT_MANIFEST_PATH} at. Empty reads the default branch.`}>
            <Input value={ref} onChange={edit(setRef)} placeholder="main or a commit SHA" className="font-mono" />
          </Field>
        ) : null}
      </div>
      {preview.data ? (
        <div>
          <Label action={<Mono>{preview.data.request.method} {preview.data.request.path}</Mono>}>RunPod request</Label>
          <JsonBlock value={preview.data.request.body} />
          <p className="mt-2 text-xs text-muted">
            {preview.data.request.method === 'POST'
              ? 'Creates the pod. It starts billing on the org RunPod account.'
              : 'Changes the image of the pod, which restarts it. The container disk is erased; volumes stay.'}
          </p>
        </div>
      ) : null}
      <FormActions error={preview.error ?? deploy.error}>
        {preview.isSuccess ? (
          <Button variant="primary" disabled={deploy.isPending}>
            {deploy.isPending ? <Spinner className="size-3.5" /> : <Rocket className="size-4" />}
            Deploy {tag}
          </Button>
        ) : (
          <Button variant="primary" disabled={!TAG_PATTERN.test(tag) || preview.isPending}>
            {preview.isPending ? <Spinner className="size-3.5" /> : null}
            Preview
          </Button>
        )}
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function RollbackPanel({ prefix, app, onDone }: { prefix: string; app: App; onDone: () => void }) {
  const invalidate = useInvalidate(prefix);
  const preview = useQuery({
    queryKey: ['app-rollback', prefix, app.name, app.current_tag],
    queryFn: () => send<DeployPreview>(`/api/dashboard/${prefix}/apps/${app.name}/rollback`, 'POST', { dry_run: true }),
    retry: false,
    gcTime: 0,
  });
  const rollback = useMutation({
    mutationFn: () => send(`/api/dashboard/${prefix}/apps/${app.name}/rollback`, 'POST', {}),
    onSuccess: () => {
      invalidate(app.name);
      onDone();
    },
  });
  const target = preview.data?.tag;
  return (
    <div className="space-y-4 rounded-lg border border-line p-4">
      {preview.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> Finding the last healthy deployment
        </div>
      ) : preview.data ? (
        <>
          <p className="text-sm text-pretty">
            Deploys <Code>{target ?? 'the previous tag'}</Code> again with the manifest it ran with
            {app.current_tag ? (
              <>
                , in place of <Code>{app.current_tag}</Code>
              </>
            ) : null}
            .
          </p>
          <div>
            <Label action={<Mono>{preview.data.request.method} {preview.data.request.path}</Mono>}>RunPod request</Label>
            <JsonBlock value={preview.data.request.body} />
          </div>
        </>
      ) : null}
      <FormActions error={preview.error ?? rollback.error}>
        <Button variant="primary" disabled={!preview.isSuccess || rollback.isPending} onClick={() => rollback.mutate()}>
          {rollback.isPending ? <Spinner className="size-3.5" /> : <History className="size-4" />}
          Roll back{target ? ` to ${target}` : ''}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </div>
  );
}

function DeletePanel({
  prefix,
  app,
  onDone,
  onDeleted,
}: {
  prefix: string;
  app: App;
  onDone: () => void;
  onDeleted: (name: string, podId: string | null) => void;
}) {
  const invalidate = useInvalidate(prefix);
  const [typed, setTyped] = useState('');
  const remove = useMutation({
    mutationFn: () => send<{ deleted: boolean; pod_id: string | null }>(`/api/dashboard/${prefix}/apps/${app.name}`, 'DELETE'),
    onSuccess: (result) => {
      invalidate();
      onDeleted(app.name, result.pod_id);
    },
  });
  return (
    <form
      className="space-y-4 rounded-lg border border-bad/30 bg-bad/5 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (typed === app.name) remove.mutate();
      }}
    >
      <div className="space-y-1 text-sm text-pretty">
        <p className="font-medium">Delete {app.name} and its deployment history?</p>
        <p className="text-muted">
          {app.pod_id ? (
            <>
              The pod <Mono className="text-fg">{app.pod_id}</Mono> is not deleted. It keeps running and billing until you
              terminate it in RunPod.
            </>
          ) : (
            'The app has no pod, so nothing runs on RunPod.'
          )}
        </p>
      </div>
      <Field label={`Type ${app.name} to confirm`}>
        <Input value={typed} onChange={(e) => setTyped(e.target.value)} className="font-mono" autoComplete="off" autoFocus />
      </Field>
      <FormActions error={remove.error}>
        <Button variant="danger" disabled={typed !== app.name || remove.isPending}>
          <Trash2 className="size-4" /> Delete app
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

function ManifestSection({ prefix, app }: { prefix: string; app: App }) {
  const invalidate = useInvalidate(prefix);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const parsed = readManifest(text);
  const save = useMutation({
    mutationFn: () =>
      send<App>(
        `/api/dashboard/${prefix}/apps/${app.name}`,
        'PUT',
        app.repo ? { repo: app.repo, manifest_path: app.manifest_path } : { manifest: parsed.manifest },
      ),
    onSuccess: () => {
      invalidate(app.name);
      setEditing(false);
    },
  });
  const action = app.repo ? (
    <Button variant="ghost" onClick={() => save.mutate()} disabled={save.isPending} title="Read the manifest file from the default branch">
      {save.isPending ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" />} Read again
    </Button>
  ) : editing ? null : (
    <Button
      variant="ghost"
      onClick={() => {
        setText(pretty(app.manifest));
        setEditing(true);
      }}
    >
      <Pencil className="size-3.5" /> Edit
    </Button>
  );
  return (
    <section>
      <Label action={action}>Manifest</Label>
      {editing ? (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (parsed.manifest) save.mutate();
          }}
        >
          <ManifestInput value={text} onChange={setText} />
          <p className="text-xs text-muted">
            env, ports, disk, args and registry apply at the next deploy. gpu, cpu, cloud, data centers and mounts apply only when
            a pod is created.
          </p>
          <FormActions error={save.error}>
            <Button variant="primary" disabled={!parsed.manifest || save.isPending}>
              Save manifest
            </Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </FormActions>
        </form>
      ) : (
        <>
          <JsonBlock value={app.manifest} />
          {app.repo ? (
            <p className="mt-2 text-xs text-muted">
              Read from <Mono className="text-fg">{app.manifest_path ?? DEFAULT_MANIFEST_PATH}</Mono> in {app.repo}. A deploy reads
              it again at its git ref; change it with a pull request.
            </p>
          ) : null}
          {save.error ? (
            <div className="mt-2">
              <ErrorNote error={save.error} />
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function Deployments({ app }: { app: AppDetail }) {
  if (!app.deployments.length) {
    return (
      <Card>
        <EmptyState icon={Rocket} title="No deployments">
          Deploy a tag here, or from CI with an apps:deploy token.
        </EmptyState>
      </Card>
    );
  }
  return (
    <Card>
      <Table>
        <thead>
          <tr>
            <Th>Tag</Th>
            <Th>Status</Th>
            <Th className="hidden md:table-cell">Actor</Th>
            <Th className="hidden sm:table-cell">Started</Th>
            <Th className="hidden lg:table-cell">Took</Th>
          </tr>
        </thead>
        <tbody>
          {app.deployments.map((d) => (
            <Tr key={d.id}>
              <Td className="w-full max-w-0 py-2.5">
                <div className="flex min-w-0 items-center gap-2">
                  <Mono className="truncate text-fg" title={d.tag}>
                    {d.tag}
                  </Mono>
                  {d.tag === app.current_tag && d.id === app.deployments.find((x) => x.tag === app.current_tag)?.id ? (
                    <Badge>current</Badge>
                  ) : null}
                </div>
                {d.error ? (
                  <div className="mt-0.5 truncate text-xs text-bad" title={d.error}>
                    {d.error}
                  </div>
                ) : d.manifest_ref ? (
                  <div className="mt-0.5 flex items-center gap-1 truncate text-xs text-muted">
                    <GitBranch className="size-3 shrink-0" />
                    <span className="truncate font-mono">{d.manifest_ref}</span>
                  </div>
                ) : null}
              </Td>
              <Td>
                <Badge tone={deployTone(d.status)}>{d.status}</Badge>
              </Td>
              <Td className="hidden max-w-40 md:table-cell">
                <Mono className="block truncate" title={d.actor ?? undefined}>
                  {actorLabel(d.actor)}
                </Mono>
              </Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums sm:table-cell">{timeAgo(d.started_at)}</Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums lg:table-cell">
                {d.started_at && d.finished_at ? duration(d.started_at, d.finished_at) : d.status === 'deploying' ? 'running' : '-'}
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

type Panel = 'deploy' | 'rollback' | 'delete' | null;

function AppPanel({ prefix, name, onDeleted }: { prefix: string; name: string; onDeleted: (name: string, podId: string | null) => void }) {
  const [panel, setPanel] = useState<Panel>(null);
  const detail = useQuery({
    queryKey: ['app', prefix, name],
    queryFn: () => api<AppDetail>(`/api/dashboard/${prefix}/apps/${name}`),
    refetchInterval: (q) => (q.state.data?.deployments.some((d) => d.status === 'deploying') ? 10_000 : false),
  });
  if (detail.isLoading) return <SkeletonRows rows={5} />;
  if (detail.error || !detail.data) return <ErrorNote error={detail.error ?? 'No data'} />;
  const app = detail.data;
  const latest = app.latest_deployment;
  const close = () => setPanel(null);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Fact label="Status">
          <Badge tone={deployTone(latest?.status ?? null)}>{latest?.status ?? 'not deployed'}</Badge>
        </Fact>
        <Fact label="Current tag">
          <Mono className="text-fg">{app.current_tag ?? '-'}</Mono>
        </Fact>
        <Fact label="Last deploy">
          <span className="text-muted tabular-nums">{timeAgo(latest?.started_at)}</span>
        </Fact>
        <Fact label="Source">
          {app.repo ? (
            <span className="inline-flex max-w-full items-center gap-1.5">
              <GitBranch className="size-3.5 shrink-0 text-muted" />
              <span className="truncate">{app.repo}</span>
            </span>
          ) : (
            <span className="text-muted">inline manifest</span>
          )}
        </Fact>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant={panel === 'deploy' ? 'primary' : 'secondary'} onClick={() => setPanel(panel === 'deploy' ? null : 'deploy')}>
          <Rocket className="size-4" /> Deploy
        </Button>
        <Button onClick={() => setPanel(panel === 'rollback' ? null : 'rollback')} title="Deploy the last healthy tag again">
          <History className="size-4" /> Roll back
        </Button>
        <Button variant="danger" className="sm:ml-auto" onClick={() => setPanel(panel === 'delete' ? null : 'delete')}>
          <Trash2 className="size-4" /> Delete
        </Button>
      </div>
      {panel === 'deploy' ? <DeployPanel prefix={prefix} app={app} onDone={close} /> : null}
      {panel === 'rollback' ? <RollbackPanel prefix={prefix} app={app} onDone={close} /> : null}
      {panel === 'delete' ? <DeletePanel prefix={prefix} app={app} onDone={close} onDeleted={onDeleted} /> : null}

      <section>
        <Label>Pod</Label>
        <PodStatus prefix={prefix} app={app} />
      </section>

      <section>
        <Label>Deployments</Label>
        <Deployments app={app} />
      </section>

      <ManifestSection key={app.updated_at} prefix={prefix} app={app} />
    </div>
  );
}

// Page

function AppTable({ apps, onOpen }: { apps: App[]; onOpen: (name: string) => void }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>App</Th>
          <Th className="hidden lg:table-cell">Host</Th>
          <Th className="hidden sm:table-cell">Tag</Th>
          <Th>Status</Th>
          <Th className="hidden md:table-cell">Last deploy</Th>
          <Th>
            <span className="sr-only">Open</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {apps.map((app) => {
          const latest = app.latest_deployment;
          const tone = deployTone(latest?.status ?? null);
          return (
            <Tr key={app.name} className="cursor-pointer" onClick={() => onOpen(app.name)}>
              <Td className="w-full max-w-0">
                <div className="flex items-center gap-2.5">
                  <Dot tone={tone} />
                  <div className="min-w-0">
                    <button
                      type="button"
                      className="block max-w-full truncate rounded-sm text-left font-medium focus-visible:outline-2 focus-visible:outline-ring"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpen(app.name);
                      }}
                    >
                      {app.name}
                    </button>
                    {app.url ? (
                      <a
                        href={app.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex max-w-full items-center gap-1 truncate text-xs text-muted hover:text-fg hover:underline"
                      >
                        {new URL(app.url).host}
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : null}
                    <div className={cx('truncate text-xs', latest?.error ? 'text-bad' : 'text-muted')}>
                      {latest?.status === 'failed' && latest.error
                        ? latest.error
                        : app.description
                          ? app.description
                          : app.repo
                          ? `${app.repo}${app.manifest_path && app.manifest_path !== DEFAULT_MANIFEST_PATH ? ` · ${app.manifest_path}` : ''}`
                          : 'inline manifest'}
                    </div>
                  </div>
                </div>
              </Td>
              <Td className="hidden lg:table-cell">
                <Badge>{HOSTS[app.host] ?? app.host}</Badge>
              </Td>
              <Td className="hidden max-w-40 sm:table-cell">
                <Mono className="block truncate text-fg">{app.current_tag ?? '-'}</Mono>
              </Td>
              <Td>
                <Badge tone={tone}>{latest?.status ?? 'not deployed'}</Badge>
              </Td>
              <Td className="hidden text-xs whitespace-nowrap text-muted tabular-nums md:table-cell">
                {latest ? (
                  <>
                    {timeAgo(latest.started_at)}
                    {latest.actor ? <span className="text-muted/70"> · {actorLabel(latest.actor)}</span> : null}
                  </>
                ) : (
                  'never'
                )}
              </Td>
              <Td className="w-8 pl-0 text-muted">
                <ChevronRight className="size-4" />
              </Td>
            </Tr>
          );
        })}
      </tbody>
    </Table>
  );
}

export function AppsPage() {
  const { prefix } = useCurrentOrg();
  const [registering, setRegistering] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<ReactNode>(null);
  const list = useQuery({
    queryKey: ['apps', prefix],
    queryFn: () => api<{ apps: App[] }>(`/api/dashboard/${prefix}/apps`),
    enabled: Boolean(prefix),
    refetchInterval: (q) => (q.state.data?.apps.some((a) => a.latest_deployment?.status === 'deploying') ? 10_000 : false),
  });
  const apps = list.data?.apps ?? [];
  const register = (
    <Button variant="primary" onClick={() => setRegistering(true)}>
      <Plus className="size-4" /> Register app
    </Button>
  );
  const current = apps.find((a) => a.name === open);
  return (
    <>
      <PageHeader
        title="Apps"
        description="The org's own bots, agents, sites and services. Register a manifest, then deploy image tags here or from CI with an apps:deploy token. Apps run on RunPod today; the host is shown per app."
        action={register}
      />
      {notice ? (
        <div role="status" className="mb-4 flex items-start gap-3 rounded-md border border-line bg-panel-2 px-3 py-2 text-sm">
          <div className="min-w-0 flex-1 text-pretty">{notice}</div>
          <button type="button" aria-label="Dismiss" className="text-muted hover:text-fg" onClick={() => setNotice(null)}>
            <X className="size-4" />
          </button>
        </div>
      ) : null}
      {list.error ? (
        <div className="mb-4">
          <ErrorNote error={list.error} />
        </div>
      ) : null}
      {list.isLoading ? (
        <Card>
          <SkeletonRows />
        </Card>
      ) : apps.length ? (
        <div className="grid gap-6">
          {KINDS.filter((k) => apps.some((a) => a.kind === k.kind)).map((k) => {
            const group = apps.filter((a) => a.kind === k.kind);
            return (
              <Card key={k.kind}>
                <CardHeader title={k.title} hint={`${k.hint} · ${group.length} ${group.length === 1 ? 'app' : 'apps'}`} />
                <AppTable apps={group} onOpen={setOpen} />
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState icon={Boxes} title="No apps" action={register}>
            Register a bot, agent, site or service with its manifest: what it is, the image, the GPU or CPU, ports, env and a health path.
          </EmptyState>
        </Card>
      )}

      <Dialog
        open={registering}
        onClose={() => setRegistering(false)}
        title="Register app"
        description="Deploys use the org secret runpod_api_key. Set it and any app_ secrets in Settings first."
        wide
      >
        <RegisterApp
          prefix={prefix}
          onDone={(name) => {
            setRegistering(false);
            if (name) setOpen(name);
          }}
        />
      </Dialog>

      <Dialog
        open={open !== null}
        onClose={() => setOpen(null)}
        title={open ?? ''}
        description={current ? (current.repo ? `From ${current.repo}` : 'Inline manifest') : undefined}
        wide
      >
        {open ? (
          <AppPanel
            key={open}
            prefix={prefix}
            name={open}
            onDeleted={(name, podId) => {
              setOpen(null);
              setNotice(
                podId ? (
                  <>
                    Deleted {name}. The pod <Mono className="text-fg">{podId}</Mono> still runs and bills; terminate it in RunPod.
                  </>
                ) : (
                  `Deleted ${name}.`
                ),
              );
            }}
          />
        ) : null}
      </Dialog>
    </>
  );
}
