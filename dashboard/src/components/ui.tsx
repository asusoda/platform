import type { ComponentProps, ReactNode } from 'react';
import type { Tone } from '../lib/format';

const toneText: Record<Tone, string> = {
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-bad',
  muted: 'text-muted',
  accent: 'text-accent',
};

const toneDot: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
  muted: 'bg-muted/60',
  accent: 'bg-accent animate-pulse',
};

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cx('min-w-0 rounded-xl border border-line bg-panel', className)} {...props} />;
}

export function CardHeader({ title, action, hint }: { title: ReactNode; action?: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-sm font-medium">{title}</h2>
        {hint ? <p className="mt-0.5 truncate text-xs text-muted">{hint}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function Stat({ label, value, sub, icon }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {sub ? <div className="mt-1 text-xs text-muted">{sub}</div> : null}
    </Card>
  );
}

export function Dot({ tone }: { tone: Tone }) {
  return <span className={cx('inline-block size-2 shrink-0 rounded-full', toneDot[tone])} />;
}

export function Badge({ tone = 'muted', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border border-line bg-panel-2 px-2 py-0.5 text-xs',
        toneText[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  variant = 'default',
  className,
  ...props
}: ComponentProps<'button'> & { variant?: 'default' | 'primary' | 'ghost' | 'danger' }) {
  const styles = {
    default: 'border border-line bg-panel-2 hover:bg-line/60',
    primary: 'bg-accent text-accent-fg hover:opacity-90',
    ghost: 'hover:bg-panel-2',
    danger: 'border border-line text-bad hover:bg-bad/10',
  }[variant];
  return (
    <button
      className={cx(
        'inline-flex h-8 items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-medium transition disabled:opacity-50',
        styles,
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cx(
        'h-9 w-full rounded-lg border border-line bg-panel px-3 text-sm outline-none placeholder:text-muted focus:border-accent',
        className,
      )}
      {...props}
    />
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

export function Switch({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        'relative h-5 w-9 shrink-0 rounded-full transition disabled:opacity-50',
        checked ? 'bg-ok' : 'bg-line',
      )}
    >
      <span className={cx('absolute top-0.5 size-4 rounded-full bg-white shadow transition', checked ? 'left-4.5' : 'left-0.5')} />
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="px-4 py-8 text-center text-sm text-muted">{children}</div>;
}

export function Spinner() {
  return <div className="size-4 animate-spin rounded-full border-2 border-line border-t-fg" />;
}

export function Loading() {
  return (
    <div className="flex h-40 items-center justify-center">
      <Spinner />
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return <div className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">{message}</div>;
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Row({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('flex items-center gap-3 border-b border-line px-4 py-3 last:border-0', className)}>{children}</div>;
}
