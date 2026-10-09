// Dialogs and form footers.
import { X } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import { Button } from './controls';
import { cx } from './cx';
import { ErrorNote } from './feedback';

// How long the close animation of a dialog lasts, in index.css.
const DIALOG_OUT_MS = 170;

// A modal panel on the native dialog element. Escape and a click on the backdrop close it.
// While it closes, it keeps the last open content, so the panel does not go empty during the animation.
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
  const last = useRef({ title, description, children });
  const [closing, setClosing] = useState(false);
  if (open) last.current = { title, description, children };
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setClosing(false);
      dialog.showModal();
    }
    if (!open && dialog.open) {
      setClosing(true);
      dialog.close();
      const timer = window.setTimeout(() => setClosing(false), DIALOG_OUT_MS);
      return () => window.clearTimeout(timer);
    }
  }, [open]);
  const shown = open ? { title, description, children } : last.current;
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClose={() => {
        if (open) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cx(
        'ui-dialog m-auto w-[calc(100%-2rem)] rounded-xl border border-line bg-panel p-0 text-fg shadow-2xl shadow-black/20',
        wide ? 'max-w-3xl' : 'max-w-lg',
      )}
    >
      {open || closing ? (
        <div className="max-h-[85vh] overflow-y-auto overscroll-contain">
          <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-line bg-panel px-5 py-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold tracking-tight">{shown.title}</h2>
              {shown.description ? <p className="mt-1 text-sm text-pretty text-muted">{shown.description}</p> : null}
            </div>
            <Button variant="ghost" size="icon" aria-label="Close" className="-mt-1 -mr-2" onClick={onClose}>
              <X className="size-4" />
            </Button>
          </div>
          <div className="p-5">{shown.children}</div>
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
