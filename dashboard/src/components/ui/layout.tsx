// Page frame: headers, cards, rows and stats.
import { type ComponentProps, type ReactNode } from 'react';
import { cx } from './cx';

// The title of a page: the sidebar label of the page, one line of description, and the page actions on the right.
export function PageHeader({ title, description, action }: { title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 flex-1 basis-72">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-pretty text-muted">{description}</p> : null}
      </div>
      {action ? <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div> : null}
    </header>
  );
}

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cx('min-w-0 overflow-hidden rounded-xl border border-line bg-panel', className)} {...props} />;
}

export function CardHeader({ title, action, hint }: { title: ReactNode; action?: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-sm font-medium">{title}</h2>
        {hint ? <p className="mt-0.5 text-xs text-pretty text-muted">{hint}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export const quietLink = 'rounded-sm text-xs text-muted transition-colors hover:text-fg';

export function Row({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx('flex min-h-12 items-center gap-3 border-b border-line px-4 py-2.5 last:border-0', className)}>
      {children}
    </div>
  );
}

export function Stat({ label, value, sub, icon }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <span className="truncate">{label}</span>
        {icon}
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {sub ? <div className="mt-1 truncate text-xs text-muted">{sub}</div> : null}
    </Card>
  );
}

// A row of Stat cards: two columns, four on a wide screen.
export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('grid grid-cols-2 gap-3 lg:grid-cols-4', className)}>{children}</div>;
}
