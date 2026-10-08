import { X } from 'lucide-react';
import { type ComponentProps, type ComponentType, type ReactNode, useEffect, useRef } from 'react';
import type { Tone } from '../lib/format';

const toneBadge: Record<Tone, string> = {
  ok: 'border-ok/25 bg-ok/10 text-ok',
  warn: 'border-warn/25 bg-warn/10 text-warn',
  bad: 'border-bad/25 bg-bad/10 text-bad',
  muted: 'border-line bg-panel-2 text-muted',
  active: 'border-info/25 bg-info/10 text-info',
};

const toneDot: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
  muted: 'bg-muted/50',
  active: 'bg-info animate-pulse',
};

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

// Layout

export function PageHeader({ title, description, action }: { title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-pretty text-muted">{description}</p> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
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

// Tables

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="overflow-x-auto">
      <table className={cx('w-full border-collapse text-left text-sm', className)} {...props} />
    </div>
  );
}

export function Th({ className, ...props }: ComponentProps<'th'>) {
  return (
    <th
      className={cx(
        'h-9 border-b border-line bg-panel-2/50 px-4 text-xs font-medium whitespace-nowrap text-muted',
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cx('h-12 border-b border-line px-4 align-middle', className)} {...props} />;
}

export function Tr({ className, ...props }: ComponentProps<'tr'>) {
  return <tr className={cx('transition-colors hover:bg-panel-2/40 [&:last-child>td]:border-0', className)} {...props} />;
}

// Text and status

export function Mono({ className, ...props }: ComponentProps<'span'>) {
  return <span className={cx('font-mono text-xs text-muted', className)} {...props} />;
}

export function Code({ className, ...props }: ComponentProps<'code'>) {
  return (
    <code
      className={cx('rounded border border-line bg-panel-2 px-1.5 py-0.5 font-mono text-[11px] whitespace-nowrap', className)}
      {...props}
    />
  );
}

export function Dot({ tone }: { tone: Tone }) {
  return <span className={cx('inline-block size-2 shrink-0 rounded-full', toneDot[tone])} />;
}

export function Badge({ tone = 'muted', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex h-5 shrink-0 items-center gap-1 rounded-md border px-1.5 text-xs font-medium whitespace-nowrap',
        toneBadge[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// Controls

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg shadow-xs hover:opacity-85',
  secondary: 'border border-line bg-panel shadow-xs hover:bg-panel-2',
  ghost: 'text-muted hover:bg-panel-2 hover:text-fg',
  danger: 'border border-line bg-panel text-bad shadow-xs hover:border-bad/40 hover:bg-bad/10',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ComponentProps<'button'> & { variant?: ButtonVariant; size?: 'md' | 'icon' }) {
  return (
    <button
      className={cx(
        'inline-flex h-8 shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md text-sm font-medium whitespace-nowrap transition disabled:pointer-events-none disabled:opacity-50',
        size === 'icon' ? 'w-8' : 'px-3',
        buttonStyles[variant],
        className,
      )}
      {...props}
    />
  );
}

const fieldClass =
  'w-full rounded-md border border-line bg-panel text-sm shadow-xs transition-colors outline-none placeholder:text-muted/70 hover:border-line-strong focus-visible:border-ring focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ring/30 aria-invalid:border-bad/60 disabled:opacity-50';

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cx(fieldClass, 'h-9 px-3', className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cx(fieldClass, 'h-9 cursor-pointer px-2.5', className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea className={cx(fieldClass, 'min-h-28 p-3', className)} {...props} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-sm font-medium">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        'relative h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors disabled:cursor-default disabled:opacity-50',
        checked ? 'border-fg bg-fg' : 'border-line-strong bg-panel-2',
      )}
    >
      <span
        className={cx(
          'absolute top-0.5 size-3.5 rounded-full shadow-sm transition-all',
          checked ? 'left-[18px] bg-bg' : 'left-0.5 bg-panel',
        )}
      />
    </button>
  );
}

// States

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
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} className="space-y-3 p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-14" />
            </Card>
          ))}
        </div>
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
    <div role="alert" className="rounded-md border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">
      {message}
    </div>
  );
}

// Overlays

// A modal panel on the native dialog element. Escape and a click on the backdrop close it.
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cx(
        'm-auto w-[calc(100%-2rem)] rounded-xl border border-line bg-panel p-0 text-fg shadow-xl backdrop:bg-black/40 backdrop:backdrop-blur-[1px]',
        wide ? 'max-w-3xl' : 'max-w-lg',
      )}
    >
      {open ? (
        <div className="max-h-[85vh] overflow-y-auto">
          <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight">{title}</h2>
              {description ? <p className="mt-1 text-sm text-pretty text-muted">{description}</p> : null}
            </div>
            <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
              <X className="size-4" />
            </Button>
          </div>
          <div className="p-5">{children}</div>
        </div>
      ) : null}
    </dialog>
  );
}

// Form footer: the actions on the left, an error after them.
export function FormActions({ children, error }: { children: ReactNode; error?: unknown }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
      {children}
      {error ? <ErrorNote error={error} /> : null}
    </div>
  );
}
