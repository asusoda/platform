import { type ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

type Side = 'right' | 'top' | 'bottom';

// The key name of Ctrl on this computer: the Command sign on a Mac.
export const MOD_KEY = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl';

// Time of the last hide. A tooltip that opens soon after another one opens with no delay.
let lastHide = 0;

const position: Record<Side, (r: DOMRect) => { left: number; top: number; transform: string }> = {
  right: (r) => ({ left: r.right + 8, top: r.top + r.height / 2, transform: 'translateY(-50%)' }),
  top: (r) => ({ left: r.left + r.width / 2, top: r.top - 6, transform: 'translate(-50%, -100%)' }),
  bottom: (r) => ({ left: r.left + r.width / 2, top: r.bottom + 6, transform: 'translateX(-50%)' }),
};

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-current/25 px-1 font-sans text-[10px] leading-none opacity-80">
      {children}
    </kbd>
  );
}

// A label that shows next to its child on hover and keyboard focus. The child keeps its own aria-label.
// The tooltip is fixed to the viewport in a portal, so a scroll box does not clip it.
export function Tooltip({
  label,
  keys,
  side = 'right',
  disabled = false,
  children,
}: {
  label: ReactNode;
  keys?: string[];
  side?: Side;
  disabled?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const id = useId();

  const show = (delay: number) => {
    window.clearTimeout(timer.current);
    const target = ref.current?.firstElementChild;
    if (!target) return;
    const wait = Date.now() - lastHide < 400 ? 0 : delay;
    timer.current = window.setTimeout(() => setRect(target.getBoundingClientRect()), wait);
  };
  const hide = () => {
    window.clearTimeout(timer.current);
    setRect((r) => {
      if (r) lastHide = Date.now();
      return null;
    });
  };

  // Moves the tooltip back into the viewport when it goes past the left or right edge.
  const tip = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = tip.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const shift = box.left < 8 ? 8 - box.left : box.right > innerWidth - 8 ? innerWidth - 8 - box.right : 0;
    if (shift) el.style.marginLeft = `${shift}px`;
  }, [rect]);

  useEffect(() => () => window.clearTimeout(timer.current), []);
  useEffect(() => {
    if (!rect) return;
    window.addEventListener('scroll', hide, true);
    return () => window.removeEventListener('scroll', hide, true);
  }, [rect]);

  return (
    <span
      ref={ref}
      className="contents"
      onMouseEnter={disabled ? undefined : () => show(350)}
      onMouseLeave={hide}
      onFocus={disabled ? undefined : (e) => (e.target as HTMLElement).matches(':focus-visible') && show(0)}
      onBlur={hide}
      onPointerDown={hide}
    >
      {children}
      {rect && !disabled
        ? createPortal(
            <span
              ref={tip}
              id={id}
              role="tooltip"
              style={{ position: 'fixed', ...position[side](rect) }}
              className="pointer-events-none z-50 flex animate-[ui-fade_120ms_var(--ease-out)] items-center gap-2 rounded-md bg-fg px-2 py-1 text-xs font-medium whitespace-nowrap text-bg shadow-md"
            >
              {label}
              {keys?.length ? (
                <span className="flex gap-0.5">
                  {keys.map((k) => (
                    <Kbd key={k}>{k}</Kbd>
                  ))}
                </span>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
