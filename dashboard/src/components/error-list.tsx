import { Check, ChevronRight, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import type { ErrorContext, ErrorGroup } from '../lib/types';
import { compact, timeAgo } from '../lib/format';
import { Checkbox } from './selection';
import { Badge, Button, cx, Dot } from './ui';

const SOURCE_LABEL: Record<ErrorGroup['source'], string> = {
  api: 'API',
  bot: 'Bot',
  worker: 'Job worker',
  mcp: 'MCP',
  browser: 'Dashboard',
};

// The context keys in the order the details show them.
const CONTEXT: [keyof ErrorContext, string][] = [
  ['request', 'Request'],
  ['job', 'Job'],
  ['logger', 'Logger'],
  ['line', 'Logged at'],
  ['release', 'Release'],
  ['host', 'Host'],
  ['pid', 'Process'],
  ['thread', 'Thread'],
  ['python', 'Python'],
];

// A line of a Python traceback that names a file. Platform frames are outside site-packages and the standard library.
const FRAME = /^\s*File "([^"]+)", line (\d+), in (.+)$/;

function isLibrary(file: string): boolean {
  return /site-packages|dist-packages|\/\.venv\/|\/lib\/python\d/.test(file);
}

// The stack trace with Platform frames in full color and library frames dimmed or hidden.
function Stack({ text }: { text: string }) {
  const [mine, setMine] = useState(false);
  const lines = text.split('\n');
  const frames = lines.filter((l) => FRAME.test(l));
  const hidden = new Set<number>();
  if (mine) {
    lines.forEach((line, i) => {
      const m = FRAME.exec(line);
      if (m && isLibrary(m[1])) {
        hidden.add(i);
        if (i + 1 < lines.length && !FRAME.test(lines[i + 1])) hidden.add(i + 1);
      }
    });
  }
  return (
    <div>
      {frames.length ? (
        <div className="mb-1.5 flex items-center justify-between text-muted">
          <span>
            {frames.length} {frames.length === 1 ? 'frame' : 'frames'}, {frames.filter((l) => !isLibrary(FRAME.exec(l)![1])).length} in Platform
          </span>
          <button type="button" onClick={() => setMine((v) => !v)} className="cursor-pointer text-fg underline-offset-2 hover:underline">
            {mine ? 'Show all frames' : 'Show Platform frames only'}
          </button>
        </div>
      ) : null}
      <pre className="max-h-96 overflow-auto rounded-md border border-line bg-panel p-3 font-mono text-[12px] leading-relaxed whitespace-pre-wrap break-words">
        {lines.map((line, i) => {
          if (hidden.has(i)) return null;
          const m = FRAME.exec(line);
          const frame = m ?? (i > 0 ? FRAME.exec(lines[i - 1]) : null);
          const library = frame ? isLibrary(frame[1]) : false;
          return (
            <div key={i} className={cx(m && !library && 'font-medium text-fg', library && 'text-muted')}>
              {line || ' '}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

// The facts of the error group: when, how often, and where the last event ran.
function Details({ error }: { error: ErrorGroup }) {
  const facts: [string, string][] = [
    ['Source', SOURCE_LABEL[error.source]],
    ['Events', String(error.count)],
    ['First seen', `${timeAgo(error.first_seen)} (${new Date(error.first_seen).toLocaleString()})`],
    ['Last seen', `${timeAgo(error.last_seen)} (${new Date(error.last_seen).toLocaleString()})`],
  ];
  if (error.route) facts.push(['Route', error.route]);
  if (error.location) facts.push(['Raised in', error.location]);
  for (const [key, label] of CONTEXT) {
    const value = error.context?.[key];
    if (value !== undefined && value !== '') facts.push([label, String(value)]);
  }
  if (error.resolved_at) facts.push(['Resolved', `${timeAgo(error.resolved_at)}${error.resolved_by ? ` by ${error.resolved_by}` : ''}`]);
  return (
    <dl className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label} className="flex min-w-0 gap-2">
          <dt className="w-24 shrink-0 text-muted">{label}</dt>
          <dd className="min-w-0 truncate font-mono" title={value}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// One error group: type, message, where and when, with its details and stack trace on click.
function ErrorRow({
  error,
  showOrg,
  onChange,
  busy,
  selected,
  onSelect,
}: {
  error: ErrorGroup;
  showOrg?: boolean;
  onChange: (action: 'resolve' | 'reopen') => void;
  busy: boolean;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const resolved = Boolean(error.resolved_at);
  return (
    <li className={cx('border-b border-line last:border-0', selected && 'bg-panel-2/60')}>
      <div className="flex min-h-14 items-center gap-3 px-4 py-2.5">
        {onSelect ? <Checkbox checked={Boolean(selected)} onChange={onSelect} label={`Select ${error.kind}`} /> : null}
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
              {error.context?.request ?? error.route ? ` · ${error.context?.request ?? error.route}` : null}
              {error.context?.job ? ` · job ${error.context.job}` : null}
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
        <div className="space-y-3 border-t border-line bg-panel-2/40 px-4 py-3 text-xs">
          <Details error={error} />
          <Stack text={error.stack || `${error.kind}: ${error.message}`} />
        </div>
      ) : null}
    </li>
  );
}

// Error groups. With isSelected and onSelect, each row has a checkbox.
export function ErrorList({
  errors,
  showOrg,
  onChange,
  busy,
  isSelected,
  onSelect,
}: {
  errors: ErrorGroup[];
  showOrg?: boolean;
  onChange: (action: 'resolve' | 'reopen', ids: number[]) => void;
  busy: boolean;
  isSelected?: (id: number) => boolean;
  onSelect?: (id: number) => void;
}) {
  return (
    <ul>
      {errors.map((e) => (
        <ErrorRow
          key={e.id}
          error={e}
          showOrg={showOrg}
          busy={busy}
          onChange={(action) => onChange(action, [e.id])}
          selected={isSelected?.(e.id)}
          onSelect={onSelect ? () => onSelect(e.id) : undefined}
        />
      ))}
    </ul>
  );
}
