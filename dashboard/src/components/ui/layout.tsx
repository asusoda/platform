// Page frame: headers, cards, rows and stats.
import { ArrowLeft, BookOpen } from 'lucide-react';
import { Link } from 'react-router';
import { type ComponentProps, createContext, type ReactNode, useContext } from 'react';
import { docsPage } from '../../lib/links';
import { cx } from './cx';

// The name, one line of description and docs page of the current page, from the page registry. The shell sets it,
// so the header of each page matches its sidebar item.
export type PageMeta = { label: string; description?: string; docs?: string };

const PageMetaContext = createContext<PageMeta | undefined>(undefined);

export const PageMetaProvider = PageMetaContext.Provider;

export function usePageMeta(): PageMeta | undefined {
  return useContext(PageMetaContext);
}

// A link to a page of the docs, for the right side of a header.
export function DocsLink({ page, className }: { page: string; className?: string }) {
  return (
    <a
      href={docsPage(page)}
      target="_blank"
      rel="noreferrer"
      className={cx('flex h-8 items-center gap-1.5 rounded-md px-2 text-xs text-muted transition-colors hover:bg-panel-2 hover:text-fg', className)}
    >
      <BookOpen className="size-3.5" /> Docs
    </a>
  );
}

// The title of a page: the sidebar label, one short line of description, a docs link and the page actions on the
// right. Title, description and docs come from the page registry when the page does not pass them. A page that passes
// its own title, such as one knowledge source, gets no description from the registry.
export function PageHeader({
  title,
  description,
  action,
  docs,
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  docs?: string;
}) {
  const meta = usePageMeta();
  if (title === undefined) {
    title = meta?.label;
    description ??= meta?.description;
  }
  docs ??= meta?.docs;
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 flex-1 basis-72">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-pretty text-muted">{description}</p> : null}
      </div>
      {action || docs ? (
        <div className="flex max-w-full shrink-0 flex-wrap items-center gap-2">
          {docs ? <DocsLink page={docs} /> : null}
          {action}
        </div>
      ) : null}
    </header>
  );
}

// A link back to the parent page, above the header of a page that one row of a list opens.
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="mb-4 inline-flex items-center gap-1.5 rounded-sm text-sm text-muted transition-colors hover:text-fg">
      <ArrowLeft className="size-4" /> {children}
    </Link>
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
