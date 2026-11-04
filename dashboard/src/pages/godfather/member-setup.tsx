import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Dialog, Field, FormActions, Input, Textarea } from '../../components/ui';
import { send } from '../../lib/api';
import type { MemberSetup, Pod } from '../../lib/types';
import { podPath, useRefreshGodfather } from './shared';

// The member setup of a pod: a repo cloned and a script run in each member's folder on their next connection.
// Off when both are empty. Pods need godfather-base 2.4.0 or later.

export const NO_SETUP: MemberSetup = { repo: '', script: '' };

// The request value: null turns member setup off.
export function setupBody(setup: MemberSetup): MemberSetup | null {
  return setup.repo.trim() || setup.script.trim() ? { repo: setup.repo.trim(), script: setup.script } : null;
}

export function MemberSetupFields({ value, onChange }: { value: MemberSetup; onChange: (v: MemberSetup) => void }) {
  return (
    <div className="grid gap-4">
      <Field label="Repo to clone" hint="A public https git URL. Cloned into each member's folder.">
        <Input
          value={value.repo}
          onChange={(e) => onChange({ ...value, repo: e.target.value })}
          placeholder="https://github.com/org/workshop.git"
          maxLength={300}
          className="font-mono text-xs"
        />
      </Field>
      <Field label="Setup script" hint="Runs with bash as the member, in their folder, after the clone.">
        <Textarea
          value={value.script}
          onChange={(e) => onChange({ ...value, script: e.target.value })}
          placeholder="pip install --user -r workshop/requirements.txt"
          maxLength={20000}
          spellCheck={false}
          className="font-mono text-xs"
        />
      </Field>
    </div>
  );
}

export function MemberSetupDialog({ prefix, pod, onClose }: { prefix: string; pod: Pod; onClose: () => void }) {
  const [setup, setSetup] = useState<MemberSetup>(pod.member_setup ?? NO_SETUP);
  const refresh = useRefreshGodfather(prefix);
  const save = useMutation({
    mutationFn: () => send(podPath(prefix, pod.id), 'PUT', { member_setup: setupBody(setup) }),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  return (
    <Dialog
      open
      onClose={onClose}
      wide
      title={`Member setup for ${pod.name}`}
      description="Each member gets it once on their next connection, and again after you change it. Leave both empty to turn it off."
    >
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <MemberSetupFields value={setup} onChange={setSetup} />
        <FormActions error={save.error}>
          <Button variant="primary" disabled={save.isPending}>
            Save setup
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </FormActions>
      </form>
    </Dialog>
  );
}
