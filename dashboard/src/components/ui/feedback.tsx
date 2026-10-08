// Empty, loading and error states, notices, and the footer of long lists.
import { X } from 'lucide-react';
import { type ComponentType, type ReactNode, useState } from 'react';
import { count } from '../../lib/format';
import { Button } from './controls';
import { cx } from './cx';
import { Card, StatGrid } from './layout';

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon?: ComponentType<{ className?: string }>;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      {Icon ? (
        <span className="mb-3 flex size-9 items-center justify-center rounded-lg border border-line bg-panel-2 text-muted">
          <Icon className="size-4" />
        </span>
      ) : null}
      {title ? <p className="text-sm font-medium">{title}</p> : null}
      {children ? <div className={cx('max-w-sm text-sm text-pretty text-muted', title && 'mt-1')}>{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded-md bg-panel-2', className)} />;
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex h-12 items-center gap-3 border-b border-line px-4 last:border-0">
          <Skeleton className="size-2 rounded-full" />
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

// A page placeholder in the shape of a header, a row of stats and a list.
export function PageSkeleton({ stats = false }: { stats?: boolean }) {
  return (
    <div role="status" aria-label="Loading">
      <div className="mb-8 space-y-2.5">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      {stats ? (
        <StatGrid className="mb-6">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} className="space-y-3 p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-14" />
            </Card>
          ))}
        </StatGrid>
      ) : null}
      <Card>
        <SkeletonRows rows={5} />
      </Card>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <div className={cx('size-4 animate-spin rounded-full border-2 border-line border-t-fg', className)} />;
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="animate-in rounded-md border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-pretty text-bad">
      {message}
    </div>
  );
}

// A message that an action worked.
export function OkNote({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p role="status" className={cx('animate-in rounded-md border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok', className)}>
      {children}
    </p>
  );
}

// A status message the officer can close, shown above the page content.
export function Notice({ children, onDismiss }: { children: ReactNode; onDismiss: () => void }) {
  return (
    <div
      role="status"
      className="mb-4 flex animate-in items-start gap-3 rounded-lg border border-line bg-panel py-2.5 pr-2.5 pl-3.5 text-sm shadow-xs"
    >
      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-info" aria-hidden />
      <div className="min-w-0 flex-1 text-pretty">{children}</div>
      <button
        type="button"
        aria-label="Dismiss"
        className="-my-0.5 flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted transition-colors hover:bg-panel-2 hover:text-fg"
        onClick={onDismiss}
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

// The first items of a list, step more on each call of more(). The count goes back to step when resetKey changes,
// such as when the filter changes. A refetch of the same list keeps the count.
export function useShowMore<T>(items: T[], resetKey: unknown, step = 100) {
  const [limit, setLimit] = useState(step);
  const [key, setKey] = useState(resetKey);
  if (key !== resetKey) {
    setKey(resetKey);
    setLimit(step);
  }
  return {
    shown: items.length > limit ? items.slice(0, limit) : items,
    total: items.length,
    step,
    more: () => setLimit((n) => n + step),
  };
}

// The footer of a long list: how many rows show, and a button that shows the next rows.
export function ShowMore({ list, noun }: { list: { shown: unknown[]; total: number; step: number; more: () => void }; noun: string }) {
  if (list.shown.length >= list.total) return null;
  const next = Math.min(list.step, list.total - list.shown.length);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-xs text-muted">
      <span className="tabular-nums">
        {count(list.shown.length)} of {count(list.total)} {noun}
      </span>
      <Button variant="ghost" className="h-7 px-2.5 text-xs" onClick={list.more}>
        Show {count(next)} more
      </Button>
    </div>
  );
}
