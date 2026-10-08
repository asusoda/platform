import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { OrgMark } from '../../components/org-mark';
import { Button, cx, ErrorNote, Field, Input } from '../../components/ui';
import { send } from '../../lib/api';
import { isHexColor, isHttpsUrl, readableForeground } from '../../lib/branding';
import type { Branding } from '../../lib/types';

export function BrandingForm({ prefix, name, saved }: { prefix: string; name: string; saved: Branding }) {
  const client = useQueryClient();
  const [logo, setLogo] = useState(saved.logo_url ?? '');
  const [accent, setAccent] = useState(saved.accent_color ?? '');
  const logoOk = !logo || isHttpsUrl(logo);
  const accentOk = !accent || isHexColor(accent);
  const changed = logo !== (saved.logo_url ?? '') || accent !== (saved.accent_color ?? '');
  const save = useMutation({
    mutationFn: () => send<Branding>(`/api/dashboard/${prefix}/branding`, 'PUT', { logo_url: logo, accent_color: accent }),
    onSuccess: (data) => {
      client.setQueryData(['branding', prefix], data);
      client.invalidateQueries({ queryKey: ['overview', prefix] });
    },
  });
  const preview = accent && accentOk ? { background: accent, color: readableForeground(accent) } : undefined;
  return (
    <form
      className="grid gap-6 p-4 md:grid-cols-[minmax(0,1fr)_260px]"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="space-y-5">
        <Field label="Logo URL" hint={logoOk ? 'An https image URL. Square images fit best. Leave empty for the initial.' : 'Must be an https URL.'}>
          <Input value={logo} onChange={(e) => setLogo(e.target.value.trim())} placeholder="https://example.org/logo.png" aria-invalid={!logoOk} />
        </Field>
        <Field label="Accent color" hint={accentOk ? 'Used for primary buttons and the initial when there is no logo. Leave empty for the neutral default.' : 'Must be a hex color like #1f6feb.'}>
          <div className="flex gap-2">
            <input
              type="color"
              aria-label="Pick accent color"
              value={accent && accentOk ? accent : '#808080'}
              onChange={(e) => setAccent(e.target.value)}
              className="h-9 w-12 shrink-0 cursor-pointer rounded-md border border-line bg-panel p-1 shadow-xs"
            />
            <Input value={accent} onChange={(e) => setAccent(e.target.value.trim())} placeholder="#1f6feb" className="font-mono" aria-invalid={!accentOk} />
            {accent ? (
              <Button type="button" variant="ghost" onClick={() => setAccent('')}>
                Default
              </Button>
            ) : null}
          </div>
        </Field>
        <div className="flex items-center gap-3 border-t border-line pt-4">
          <Button variant="primary" disabled={!changed || !logoOk || !accentOk || save.isPending}>
            Save branding
          </Button>
          {save.isSuccess && !changed ? <span className="text-xs text-muted">Saved</span> : null}
        </div>
        {save.error ? <ErrorNote error={save.error} /> : null}
      </div>
      <div className="space-y-3 rounded-lg border border-dashed border-line-strong bg-bg p-3">
        <div className="font-mono text-[11px] tracking-wider text-muted uppercase">Preview</div>
        <div className="flex items-center gap-2.5 rounded-lg border border-line bg-panel p-2 shadow-xs">
          <OrgMark key={logo} name={name} logoUrl={logoOk ? logo : null} className="size-8" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{name}</span>
            <span className="block truncate font-mono text-xs text-muted">{prefix}</span>
          </span>
        </div>
        <span
          className={cx('inline-flex h-8 items-center rounded-md px-3 text-sm font-medium shadow-xs', !preview && 'bg-fg text-bg')}
          style={preview}
        >
          Primary action
        </span>
      </div>
    </form>
  );
}
