import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Dialog, Field, FormActions, Input, Spinner } from '../../components/ui';
import { send } from '../../lib/api';
import { type ComputeSettings, computePath, useComputeSettings } from './shared';

// The org's default pod image. Empty uses the deployment default from .env.
export function ComputeSettingsDialog({ prefix, onClose }: { prefix: string; onClose: () => void }) {
  const current = useComputeSettings(prefix);
  return (
    <Dialog open onClose={onClose} title="Compute settings" description="New pods use these values when the officer leaves them empty.">
      {current.data ? <Form prefix={prefix} saved={current.data} onClose={onClose} /> : <Spinner className="size-4" />}
    </Dialog>
  );
}

function Form({ prefix, saved, onClose }: { prefix: string; saved: ComputeSettings; onClose: () => void }) {
  const client = useQueryClient();
  const [image, setImage] = useState(saved.pod_image ?? '');
  const save = useMutation({
    mutationFn: () => send<{ settings: ComputeSettings }>(`${computePath(prefix)}/settings`, 'PUT', { pod_image: image.trim() || null }),
    onSuccess: (body) => {
      client.setQueryData(['compute', prefix, 'settings'], body.settings);
      onClose();
    },
  });
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Field label="Default pod image" hint={`It must implement the pod contract. Leave empty for the deployment default, ${saved.deployment_pod_image}.`}>
        <Input value={image} onChange={(e) => setImage(e.target.value)} placeholder={saved.deployment_pod_image} className="font-mono text-xs" maxLength={200} />
      </Field>
      <FormActions error={save.error}>
        <Button variant="primary" disabled={save.isPending}>
          {save.isPending ? <Spinner className="size-3.5" /> : null}
          Save
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}
