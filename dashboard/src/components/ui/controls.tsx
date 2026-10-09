// Buttons and form fields.
import { Search, Trash2 } from 'lucide-react';
import { type ComponentProps, type ReactNode } from 'react';
import { cx } from './cx';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg shadow-xs hover:opacity-90 active:opacity-80',
  secondary: 'border border-line bg-panel shadow-xs hover:border-line-strong hover:bg-panel-2 active:bg-panel-2',
  ghost: 'text-muted hover:bg-panel-2 hover:text-fg active:bg-panel-2',
  danger: 'border border-line bg-panel text-bad shadow-xs hover:border-bad/40 hover:bg-bad/10 active:bg-bad/15',
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
        'inline-flex h-8 shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-[color,background-color,border-color,opacity,scale] duration-150 ease-out select-none active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50',
        size === 'icon' ? 'w-8' : 'px-3',
        buttonStyles[variant],
        className,
      )}
      {...props}
    />
  );
}

const fieldClass =
  'w-full rounded-md border border-line bg-panel text-sm shadow-xs transition-[border-color,box-shadow] duration-150 outline-none placeholder:text-muted/70 hover:border-line-strong focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 aria-invalid:border-bad/60 disabled:opacity-50';

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cx(fieldClass, 'h-9 px-3', className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cx(fieldClass, 'ui-select h-9 cursor-pointer px-2.5', className)} {...props} />;
}

// A search field with an icon. The parent filters with useDeferredValue, so typing does not wait for the list.
export function SearchInput({ className, ...props }: ComponentProps<'input'>) {
  return (
    <label className={cx('relative block', className)}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <Input type="search" autoComplete="off" spellCheck={false} className="pl-9 [&::-webkit-search-cancel-button]:hidden" {...props} />
    </label>
  );
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
        'relative h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors duration-150 disabled:cursor-default disabled:opacity-50',
        checked ? 'border-fg bg-fg' : 'border-line-strong bg-panel-2',
      )}
    >
      <span
        className={cx(
          'absolute top-0.5 left-0.5 size-3.5 rounded-full shadow-sm transition-[translate,background-color] duration-200 ease-out',
          checked ? 'translate-x-4 bg-bg' : 'translate-x-0 bg-panel',
        )}
      />
    </button>
  );
}

// An icon button that deletes after the officer confirms the question.
export function DeleteButton({
  label,
  question,
  onDelete,
  title = 'Delete',
  disabled,
  className,
}: {
  label: string;
  question: string;
  onDelete: () => void;
  title?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      title={title}
      aria-label={label}
      className={cx('hover:text-bad', className)}
      disabled={disabled}
      onClick={() => {
        if (confirm(question)) onDelete();
      }}
    >
      <Trash2 className="size-4" />
    </Button>
  );
}

// A checkbox in a bordered box, with a title and a line of description.
export function CheckOption({
  checked,
  onChange,
  title,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-line p-3 text-sm transition-colors hover:bg-panel-2/50 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring">
      <input type="checkbox" className="mt-0.5 size-4 accent-current" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{children}</span>
      </span>
    </label>
  );
}
