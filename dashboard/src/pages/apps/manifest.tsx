import { useMutation } from '@tanstack/react-query';
import { Pencil, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Button, cx, ErrorNote, FormActions, Mono, Spinner, Textarea } from '../../components/ui';
import { send } from '../../lib/api';
import type { App, AppManifest } from '../../lib/types';
import { DEFAULT_MANIFEST_PATH, JsonBlock, Label, pretty, useInvalidate } from './shared';

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

// Parses manifest JSON and checks the fields the server requires. The server checks the full schema.
export function readManifest(text: string): { manifest?: AppManifest; error?: string } {
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

export function ManifestInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
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

export function ManifestSection({ prefix, app }: { prefix: string; app: App }) {
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
