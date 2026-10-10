import { X } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import { cx } from './ui';

type Id = string | number;

// The ids selected in a list. Ids that leave the list leave the selection.
export function useSelection<T extends Id>(ids: T[]) {
  const [picked, setPicked] = useState<Set<T>>(new Set());
  const present = new Set(ids);
  const selected = new Set([...picked].filter((id) => present.has(id)));
  const all = ids.length > 0 && selected.size === ids.length;
  return {
    selected,
    ids: [...selected],
    count: selected.size,
    all,
    some: selected.size > 0 && !all,
    has: (id: T) => selected.has(id),
    toggle: (id: T) =>
      setPicked((current) => {
        const next = new Set(current);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    toggleAll: () => setPicked(all ? new Set() : new Set(ids)),
    clear: () => setPicked(new Set()),
  };
}

// A checkbox for a list row or a list header. mixed shows a dash for a partial selection.
export function Checkbox({
  checked,
  mixed = false,
  onChange,
  label,
  className,
}: {
  checked: boolean;
  mixed?: boolean;
  onChange: () => void;
  label: string;
  className?: string;
}) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input
      ref={box}
      type="checkbox"
      aria-label={label}
      checked={checked}
      onChange={onChange}
      className={cx('size-4 shrink-0 cursor-pointer rounded accent-current', className)}
    />
  );
}

// The bar above a list: select all on the left, and the actions for the selected rows on the right.
export function SelectionBar({
  count,
  total,
  all,
  some,
  onToggleAll,
  onClear,
  noun,
  children,
  extra,
}: {
  count: number;
  total: number;
  all: boolean;
  some: boolean;
  onToggleAll: () => void;
  onClear: () => void;
  noun: string;
  children?: ReactNode;
  extra?: ReactNode;
}) {
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-3 border-b border-line px-4 py-2">
      <Checkbox checked={all} mixed={some} onChange={onToggleAll} label={all ? 'Clear the selection' : `Select all ${noun}`} />
      {count ? (
        <>
          <span className="text-xs font-medium tabular-nums">{count} selected</span>
          <button
            type="button"
            onClick={onClear}
            aria-label="Clear the selection"
            className="flex size-6 cursor-pointer items-center justify-center rounded-md text-muted hover:bg-panel-2 hover:text-fg"
          >
            <X className="size-3.5" />
          </button>
          <div className="ml-auto flex flex-wrap items-center gap-2">{children}</div>
        </>
      ) : (
        <>
          <span className="text-xs text-muted tabular-nums">
            {total} {noun}
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">{extra}</div>
        </>
      )}
    </div>
  );
}
