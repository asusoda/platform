import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, LayoutTemplate } from 'lucide-react';
import { useState } from 'react';
import { Button, Card, EmptyState, ErrorNote, Field, FormActions, Input, SkeletonRows, Spinner } from '../../components/ui';
import { api, send } from '../../lib/api';
import type { AppFromTemplate, AppTemplate } from '../../lib/types';
import { firstConfigured, ProviderField, useProviders } from '../hosting/providers';
import { NAME_PATTERN, useInvalidate } from './shared';

export function useTemplates(prefix: string) {
  return useQuery({
    queryKey: ['app-templates', prefix],
    queryFn: () => api<{ templates: AppTemplate[] }>(`/api/dashboard/${prefix}/apps/templates`).then((b) => b.templates),
    enabled: Boolean(prefix),
    staleTime: 300_000,
  });
}

function TemplateForm({
  prefix,
  template,
  onBack,
  onDone,
}: {
  prefix: string;
  template: AppTemplate;
  onBack: () => void;
  onDone: (name: string, tag: string | null) => void;
}) {
  const invalidate = useInvalidate(prefix);
  const providers = useProviders(prefix);
  const [chosen, setChosen] = useState<string | null>(null);
  const provider = chosen ?? firstConfigured(providers.data);
  const [name, setName] = useState(template.name);
  const [values, setValues] = useState<Record<string, string>>({});
  const set = (key: string, value: string) => setValues((v) => ({ ...v, [key]: value }));
  const nameOk = !name || NAME_PATTERN.test(name);
  const ready = NAME_PATTERN.test(name) && template.inputs.every((i) => !i.required || values[i.key]?.trim());
  const create = useMutation({
    mutationFn: () => {
      const plain: Record<string, string> = {};
      const secret: Record<string, string> = {};
      for (const i of template.inputs) {
        const value = values[i.key]?.trim();
        if (value) (i.kind === 'secret' ? secret : plain)[i.key] = value;
      }
      return send<AppFromTemplate>(`/api/dashboard/${prefix}/apps/templates/${template.name}`, 'POST', {
        name,
        provider,
        values: plain,
        secrets: secret,
      });
    },
    onSuccess: (app) => {
      invalidate(app.name);
      onDone(app.name, app.suggested_tag);
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
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Name" hint={nameOk ? undefined : 'Lowercase letters, digits and dashes.'}>
          <Input value={name} onChange={(e) => setName(e.target.value.trim())} aria-invalid={!nameOk} required autoFocus />
        </Field>
        <ProviderField prefix={prefix} providers={providers.data} value={provider} onChange={setChosen} hint="" />
        {template.inputs.map((i) => (
          <Field key={i.key} label={i.required ? i.label : `${i.label} (optional)`}>
            <Input
              type={i.kind === 'secret' ? 'password' : 'text'}
              autoComplete="off"
              value={values[i.key] ?? ''}
              onChange={(e) => set(i.key, e.target.value)}
              className={i.kind === 'secret' ? undefined : 'font-mono'}
              required={i.required}
            />
          </Field>
        ))}
      </div>
      <FormActions error={create.error}>
        <Button variant="primary" disabled={!ready || create.isPending}>
          {create.isPending ? <Spinner className="size-3.5" /> : null}
          Create app
        </Button>
        <Button type="button" variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" /> Back
        </Button>
      </FormActions>
    </form>
  );
}

// Pick a template, fill in its inputs, create the app. onDone gets the app name and the template's tag.
export function TemplatePicker({ prefix, onDone }: { prefix: string; onDone: (name: string | null, tag?: string | null) => void }) {
  const templates = useTemplates(prefix);
  const [picked, setPicked] = useState<string | null>(null);
  const template = templates.data?.find((t) => t.name === picked);
  if (template) return <TemplateForm prefix={prefix} template={template} onBack={() => setPicked(null)} onDone={onDone} />;
  if (templates.isLoading) return <SkeletonRows rows={2} />;
  if (templates.error) return <ErrorNote error={templates.error} />;
  if (!templates.data?.length) return <EmptyState icon={LayoutTemplate} title="No templates" />;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {templates.data.map((t) => (
        <Card key={t.name} className="p-0">
          <button
            type="button"
            className="block h-full w-full cursor-pointer rounded-[inherit] p-4 text-left transition-colors hover:bg-panel-2/60 focus-visible:outline-2 focus-visible:outline-ring"
            onClick={() => setPicked(t.name)}
          >
            <span className="block font-medium">{t.title}</span>
            <span className="mt-1 block text-sm text-muted">{t.summary}</span>
          </button>
        </Card>
      ))}
    </div>
  );
}
