import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { cx } from './ui';

export type Tab<T extends string> = { id: T; label: string };

// The tab named by the ?tab= query parameter, and a function to change it. The first tab has no parameter.
export function useTabParam<T extends string>(tabs: readonly Tab<T>[]): [T, (id: T) => void] {
  const [params, setParams] = useSearchParams();
  const first = tabs[0].id;
  const tab = tabs.find((t) => t.id === params.get('tab'))?.id ?? first;
  return [tab, (id: T) => setParams(id === first ? {} : { tab: id }, { replace: true })];
}

// A row of tabs with an underline under the open one. extra adds content after a label, such as a count.
export function TabBar<T extends string>({
  label,
  tabs,
  value,
  onChange,
  extra,
}: {
  label: string;
  tabs: readonly Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  extra?: (id: T) => ReactNode;
}) {
  return (
    <div role="tablist" aria-label={label} className="mb-6 flex gap-1 border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            '-mb-px h-9 cursor-pointer border-b-2 px-3 text-sm transition-colors',
            value === t.id ? 'border-fg font-medium text-fg' : 'border-transparent text-muted hover:text-fg',
          )}
        >
          {t.label}
          {extra?.(t.id)}
        </button>
      ))}
    </div>
  );
}
