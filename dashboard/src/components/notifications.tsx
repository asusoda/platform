import { ArrowUpRight, Bell, Check, CheckCheck, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router';
import { timeAgo } from '../lib/format';
import { useCurrentOrg } from '../lib/org';
import { useNotificationChange, useNotifications } from '../lib/queries';
import type { Notification } from '../lib/types';
import { Tooltip } from './tooltip';
import { Badge, Button, cx, Mono, Spinner } from './ui';

const MODULE_LABELS: Record<string, string> = { alerts: 'Alerts', apps: 'Services', knowledge: 'Knowledge' };

export const moduleLabel = (module: string) => MODULE_LABELS[module] ?? module;

// One notification: the module, the subject, the message, a link to the page that fixes it, and resolve or reopen.
export function NotificationItem({ n, compact = false, onOpen }: { n: Notification; compact?: boolean; onOpen?: () => void }) {
  const { prefix } = useCurrentOrg();
  const change = useNotificationChange(prefix);
  const resolved = Boolean(n.resolved_at);
  const busy = change.isPending;
  return (
    <li className={cx('group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-panel-2/40', resolved && 'opacity-70')}>
      <span className={cx('mt-1.5 size-1.5 shrink-0 rounded-full', resolved ? 'bg-muted/50' : 'bg-bad')} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <Badge tone={resolved ? 'muted' : 'bad'}>{moduleLabel(n.module)}</Badge>
          <Mono className="truncate text-xs text-fg" title={n.subject}>
            {n.subject}
          </Mono>
        </div>
        <p className={cx('mt-1 text-sm break-words text-muted', compact && 'line-clamp-2')} title={n.message}>
          {n.message}
        </p>
        {resolved && !compact ? (
          <p className="mt-1 text-xs text-muted">
            Resolved {timeAgo(n.resolved_at as string)}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Tooltip label={`Open ${moduleLabel(n.module)}`} side="top">
          <Link
            to={`/${prefix}/${n.link}`}
            onClick={onOpen}
            aria-label={`Open ${moduleLabel(n.module)}`}
            className="flex size-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-panel-2 hover:text-fg"
          >
            <ArrowUpRight className="size-4" />
          </Link>
        </Tooltip>
        <Tooltip label={resolved ? 'Reopen' : 'Resolve'} side="top">
          <button
            type="button"
            disabled={busy}
            aria-label={resolved ? 'Reopen' : 'Resolve'}
            onClick={() => change.mutate({ action: resolved ? 'reopen' : 'resolve', ids: [n.id] })}
            className="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted transition-colors hover:bg-panel-2 hover:text-fg disabled:opacity-50"
          >
            {busy ? <Spinner className="size-3.5" /> : resolved ? <RotateCcw className="size-3.5" /> : <Check className="size-4" />}
          </button>
        </Tooltip>
      </div>
    </li>
  );
}

const PREVIEW = 6;

// The bell in the top bar: the count of open notifications and a panel with the newest ones.
export function NotificationsBell() {
  const { prefix } = useCurrentOrg();
  const { data } = useNotifications(prefix);
  const change = useNotificationChange(prefix);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const list = (data?.notifications ?? []).filter((n) => !n.resolved_at);
  const count = data?.open ?? 0;

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <Tooltip label="Notifications" side="bottom">
        <button
          type="button"
          aria-label={count ? `Notifications, ${count} open` : 'Notifications'}
          aria-expanded={open}
          aria-haspopup="dialog"
          onClick={() => setOpen(!open)}
          className={cx(
            'relative flex size-8 cursor-pointer items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-panel-2 hover:text-fg',
            open && 'bg-panel-2 text-fg',
          )}
        >
          <Bell className="size-4" />
          {count ? (
            <span className="absolute top-1 right-1 flex h-3.5 min-w-3.5 animate-in items-center justify-center rounded-full bg-bad px-1 text-[10px] leading-none font-semibold text-white tabular-nums ring-2 ring-bg">
              {count > 99 ? '99+' : count}
            </span>
          ) : null}
        </button>
      </Tooltip>
      {open ? (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute top-10 right-0 z-30 w-[min(400px,calc(100vw-24px))] origin-top-right animate-in overflow-hidden rounded-xl border border-line bg-panel shadow-xl"
        >
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
            <span className="text-sm font-medium">Notifications</span>
            {list.length ? (
              <Button
                variant="ghost"
                className="h-7 px-2 text-xs"
                disabled={change.isPending}
                onClick={() => change.mutate({ action: 'resolve', ids: list.map((n) => n.id) })}
              >
                <CheckCheck className="size-3.5" /> Resolve all
              </Button>
            ) : null}
          </div>
          {list.length ? (
            <ul className="max-h-[60vh] divide-y divide-line overflow-y-auto overscroll-contain">
              {list.slice(0, PREVIEW).map((n) => (
                <NotificationItem key={n.id} n={n} compact onOpen={() => setOpen(false)} />
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
              <CheckCheck className="size-5 text-muted" />
              <span className="text-sm">Nothing needs attention</span>
            </div>
          )}
          <Link
            to={`/${prefix}/notifications`}
            className="block border-t border-line px-4 py-2.5 text-center text-xs text-muted transition-colors hover:bg-panel-2/60 hover:text-fg"
          >
            {list.length > PREVIEW ? `View all ${list.length}` : 'View all notifications'}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
