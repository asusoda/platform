import { Check, ChevronRight, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import type { ErrorGroup } from '../lib/types';
import { compact, timeAgo } from '../lib/format';
import { Badge, Button, cx, Dot } from './ui';

const SOURCE_LABEL: Record<ErrorGroup['source'], string> = {
  api: 'API',
  bot: 'Bot',
  worker: 'Job worker',
  mcp: 'MCP',
  browser: 'Dashboard',
};

// One error group: type, message, where and when, with its stack trace on click.
function ErrorRow({
  error,
  showOrg,
  onChange,
  busy,
}: {
  error: ErrorGroup;
  showOrg?: boolean;
  onChange: (action: 'resolve' | 'reopen') => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const resolved = Boolean(error.resolved_at);
  return (
    <li className="border-b border-line last:border-0">
      <div className="flex min-h-14 items-center gap-3 px-4 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-left"
        >
          <ChevronRight className={cx('size-4 shrink-0 text-muted transition-transform', open && 'rotate-90')} />
          <Dot tone={resolved ? 'muted' : 'bad'} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">
              <span className="font-medium">{error.kind}</span>
              <span className="text-muted">: {error.message}</span>
            </div>
            <div className="mt-0.5 truncate text-xs text-muted">
              {SOURCE_LABEL[error.source]}
              {showOrg ? ` · ${error.org ?? 'server'}` : null}
              {error.route ? ` · ${error.route}` : null}
              {error.location && error.location !== error.route ? <span className="font-mono"> · {error.location}</span> : null}
            </div>
          </div>
        </button>
        <Badge tone={resolved ? 'muted' : 'bad'}>{compact(error.count)}×</Badge>
        <span className="hidden w-20 text-right text-xs text-muted tabular-nums sm:block" title={error.last_seen}>
          {timeAgo(error.last_seen)}
        </span>
        <Button variant="ghost" size="icon" disabled={busy} onClick={() => onChange(resolved ? 'reopen' : 'resolve')} title={resolved ? 'Reopen' : 'Resolve'} aria-label={resolved ? 'Reopen' : 'Resolve'}>
          {resolved ? <RotateCcw className="size-4" /> : <Check className="size-4" />}
        </Button>
      </div>
      {open ? (
        <div className="space-y-2 border-t border-line bg-panel-2/40 px-4 py-3 text-xs">
          <div className="text-muted">
            First seen {timeAgo(error.first_seen)}, last seen {timeAgo(error.last_seen)}.
            {error.resolved_at ? ` Resolved ${timeAgo(error.resolved_at)}${error.resolved_by ? ` by ${error.resolved_by}` : ''}.` : null}
          </div>
          <pre className="max-h-80 overflow-auto rounded-md border border-line bg-panel p-3 font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words">
            {error.stack || error.message}
          </pre>
        </div>
      ) : null}
    </li>
  );
}

export function ErrorList({
  errors,
  showOrg,
  onChange,
  busy,
}: {
  errors: ErrorGroup[];
  showOrg?: boolean;
  onChange: (action: 'resolve' | 'reopen', ids: number[]) => void;
  busy: boolean;
}) {
  return (
    <ul>
      {errors.map((e) => (
        <ErrorRow key={e.id} error={e} showOrg={showOrg} busy={busy} onChange={(action) => onChange(action, [e.id])} />
      ))}
    </ul>
  );
}
