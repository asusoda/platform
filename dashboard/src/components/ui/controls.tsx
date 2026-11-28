// Buttons and form fields.
import { Check, Minus, Search } from 'lucide-react';
import { type ComponentProps, type ReactNode, useEffect, useRef } from 'react';
import { Link } from 'react-router';
import { Tooltip } from '../tooltip';
import { cx } from './cx';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const buttonStyles: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg shadow-xs hover:opacity-90 active:opacity-80',
  secondary: 'border border-line bg-panel shadow-xs hover:border-line-strong hover:bg-panel-2 active:bg-panel-2',
  ghost: 'text-muted hover:bg-panel-2 hover:text-fg active:bg-panel-2',
  danger: 'border border-line bg-panel text-bad shadow-xs hover:border-bad/40 hover:bg-bad/10 active:bg-bad/15',
};

type ButtonSize = 'md' | 'sm' | 'icon';

const buttonSizes: Record<ButtonSize, string> = {
  md: 'h-8 px-3 text-sm',
  sm: 'h-7 px-2 text-xs',
  icon: 'size-8 text-sm',
};

// The classes of a button, for an element that is not a button, such as a link.
export function buttonClass(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', className?: string): string {
  return cx(
    'inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-[color,background-color,border-color,opacity,scale] duration-150 ease-out select-none active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50',
    buttonSizes[size],
    buttonStyles[variant],
    className,
  );
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ComponentProps<'button'> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <button className={buttonClass(variant, size, className)} {...props} />;
}

// A link to a dashboard page that looks like a button.
export function LinkButton({
  variant = 'secondary',
  size = 'md',
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}

// A ghost button with only an icon. The label is its accessible name and its tooltip.
export function IconButton({
  label,
  className,
  children,
  ...props
}: Omit<ComponentProps<'button'>, 'aria-label'> & { label: string }) {
  return (
    <Tooltip label={label} side="top">
      <button type="button" aria-label={label} className={buttonClass('ghost', 'icon', className)} {...props}>
        {children}
      </button>
    </Tooltip>
  );
}

// A button that reads as text: a row title that opens its details, or a small action in a line of text.
// quiet is muted until hover; strong is the row title; row is a block of two lines whose first line underlines.
export function TextButton({
  tone = 'quiet',
  className,
  ...props
}: ComponentProps<'button'> & { tone?: 'quiet' | 'strong' | 'row' }) {
  return (
    <button
      type="button"
      className={cx(
        'cursor-pointer rounded-sm text-left underline-offset-2 transition-colors duration-150 hover:underline disabled:pointer-events-none disabled:opacity-50',
        tone === 'quiet' && 'text-xs text-muted hover:text-fg',
        tone === 'strong' && 'min-w-0 font-medium text-fg',
        tone === 'row' && 'group block w-full min-w-0 hover:no-underline [&>:first-child]:group-hover:underline',
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

// A checkbox in the style of the app. mixed shows a dash for a partial selection. With reveal, the box shows only
// on a hover of its row (a group), on focus, when checked, or while its list has a selection (SelectionList).
export function Checkbox({
  checked,
  mixed = false,
  onChange,
  label,
  reveal = false,
  className,
}: {
  checked: boolean;
  mixed?: boolean;
  onChange: () => void;
  label: string;
  reveal?: boolean;
  className?: string;
}) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <span
      className={cx(
        'relative inline-flex size-4 shrink-0 items-center justify-center transition-opacity duration-150',
        reveal &&
          'opacity-0 group-hover:opacity-100 has-checked:opacity-100 has-focus-visible:opacity-100 [[data-selecting=true]_&]:opacity-100',
        className,
      )}
    >
      <input
        ref={box}
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={onChange}
        className="peer absolute inset-0 m-0 cursor-pointer appearance-none rounded-[5px] border border-line-strong bg-panel shadow-xs transition-colors duration-150 checked:border-fg checked:bg-fg indeterminate:border-fg indeterminate:bg-fg hover:border-fg/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      />
      <Check strokeWidth={3} className="pointer-events-none relative size-3 text-bg opacity-0 peer-checked:opacity-100" aria-hidden />
      <Minus
        strokeWidth={3}
        className="pointer-events-none absolute size-3 text-bg opacity-0 peer-indeterminate:opacity-100"
        aria-hidden
      />
    </span>
  );
}

// A checkbox with a title and a line of description, for forms.
export function CheckOption({
  checked,
  onChange,
  title,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  children?: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 rounded-md py-1 text-sm">
      <Checkbox checked={checked} onChange={() => onChange(!checked)} label={title} className="mt-0.5" />
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        {children ? <span className="mt-0.5 block text-xs text-muted">{children}</span> : null}
      </span>
    </label>
  );
}

// A row of toggle buttons in one box, such as a time range. The pressed one has a fill.
export function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
  className,
}: {
  label: string;
  options: { value: T; label: ReactNode; pressed?: boolean }[];
  value?: T;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cx('flex flex-wrap rounded-md border border-line p-0.5', className)}>
      {options.map((o) => {
        const pressed = o.pressed ?? o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            aria-pressed={pressed}
            onClick={() => onChange(o.value)}
            className={cx(
              'h-7 cursor-pointer rounded px-2.5 text-xs transition-colors duration-150',
              pressed ? 'bg-panel-2 font-medium text-fg' : 'text-muted hover:text-fg',
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
