import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Button, Card, CardHeader, Checkbox, ErrorNote, SkeletonRows, cx } from '../components/ui';
import { api, send } from '../lib/api';
import type { ToolGroupLayer, ToolGroups } from '../lib/types';

const LAYERS: { key: ToolGroupLayer; title: string }[] = [
  { key: 'base', title: 'Base' },
  { key: 'service', title: 'Services' },
  { key: 'module', title: 'Modules' },
];

// The tool groups the org's tokens can reach over MCP and /api/tools. null allows every group.
export function ToolGroupsCard({ prefix }: { prefix: string }) {
  const client = useQueryClient();
  const key = ['tool-groups', prefix];
  const groups = useQuery({ queryKey: key, queryFn: () => api<ToolGroups>(`/api/dashboard/${prefix}/tool-groups`) });
  // The officer's choice before Save; undefined means no change yet
  const [draft, setDraft] = useState<string[] | null | undefined>(undefined);
  const save = useMutation({
    mutationFn: (chosen: string[] | null) =>
      send<ToolGroups>(`/api/dashboard/${prefix}/tool-groups`, 'PUT', { groups: chosen }),
    onSuccess: (saved) => {
      client.setQueryData(key, saved);
      setDraft(undefined);
    },
  });
  const data = groups.data;
  const allowed = draft === undefined ? (data?.allowed ?? null) : draft;
  const every = allowed === null;
  const chosen = new Set(allowed ?? []);
  const toggle = (name: string) => {
    const next = new Set(chosen);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setDraft([...next].sort());
  };
  return (
    <Card className="mt-6">
      <CardHeader
        title="Tool groups"
        hint="The tools that agents and tokens of this org can call. A token also needs the scope."
        action={
          <Button
            variant="primary"
            disabled={draft === undefined || save.isPending}
            onClick={() => save.mutate(draft ?? null)}
          >
            Save
          </Button>
        }
      />
      {groups.error ? (
        <div className="px-4 py-3">
          <ErrorNote error={groups.error} />
        </div>
      ) : !data ? (
        <SkeletonRows />
      ) : (
        <div className="space-y-4 px-4 py-3 text-sm">
          <label className="flex cursor-pointer items-center gap-3">
            <Checkbox
              checked={every}
              onChange={() => setDraft(every ? data.groups.map((g) => g.key) : null)}
              label="Every group"
            />
            <span>Every group</span>
          </label>
          {LAYERS.map(({ key: layer, title }) => {
            const inLayer = data.groups.filter((g) => g.layer === layer);
            if (!inLayer.length) return null;
            return (
              <fieldset key={layer} disabled={every} className={cx('space-y-1.5', every && 'opacity-60')}>
                <legend className="mb-1.5 text-xs font-medium text-muted">{title}</legend>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3 lg:grid-cols-5">
                  {inLayer.map((group) => (
                    <label
                      key={group.key}
                      className={cx('flex items-center gap-2', every ? 'cursor-not-allowed' : 'cursor-pointer')}
                    >
                      <Checkbox
                        checked={every || chosen.has(group.key)}
                        onChange={() => !every && toggle(group.key)}
                        label={group.key}
                      />
                      <span className="font-mono text-xs">{group.key}</span>
                      {group.tools !== null ? (
                        <span className="text-xs text-muted tabular-nums">{group.tools}</span>
                      ) : null}
                    </label>
                  ))}
                </div>
              </fieldset>
            );
          })}
          {save.error ? <ErrorNote error={save.error} /> : null}
        </div>
      )}
    </Card>
  );
}
