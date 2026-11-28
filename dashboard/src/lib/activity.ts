// One timeline of what happened in an org, merged in the browser from the lists that the API already gives.

import { runTone, type Tone } from './format';
import { notificationModule } from './modules';
import type { AuditEntry, CiRepo, Delivery, KnowledgeRun, Notification } from './types';

export type TimelineKind = 'event' | 'error' | 'change' | 'run' | 'post' | 'ci';

export const TIMELINE_KINDS: { value: TimelineKind; label: string }[] = [
  { value: 'event', label: 'Events' },
  { value: 'error', label: 'Errors' },
  { value: 'change', label: 'Changes' },
  { value: 'run', label: 'Runs' },
  { value: 'post', label: 'Posts' },
  { value: 'ci', label: 'CI' },
];

export type TimelineRow = {
  // The source and the key in it, such as audit:12
  id: string;
  at: string;
  kind: TimelineKind;
  module: string;
  title: string;
  detail?: string;
  tone: Tone;
  // A dashboard path relative to /<org>/, or an outside URL
  link?: string;
  href?: string;
};

// Events and errors from the notifications. A problem is a state, not a row with a time, so it is left out.
export function fromNotifications(list: Notification[]): TimelineRow[] {
  return list
    .filter((n) => n.kind === 'event' && n.at)
    .map((n) => ({
      id: `notification:${n.id}`,
      at: n.at as string,
      kind: n.module === 'errors' ? 'error' : 'event',
      module: notificationModule(n.module),
      title: n.subject,
      detail: n.message,
      tone: n.resolved_at ? 'muted' : n.level === 'error' ? 'bad' : 'ok',
      link: n.link || undefined,
    }));
}

// The module of an audit row: the job name before the dot, or the module part of the route.
export function auditModule(action: string): string {
  const job = /^job ([a-z_]+)\./.exec(action);
  if (job) return job[1];
  const route = /\/api\/([a-z_]+)\//.exec(action);
  if (!route) return 'organizations';
  return route[1] === 'compute' ? 'godfather' : route[1] === 'apps' ? 'runpod' : route[1];
}

// Changes by officers and tokens, and job runs, from the audit log.
export function fromAudit(entries: AuditEntry[]): TimelineRow[] {
  return entries
    .filter((e) => e.created_at)
    .map((e) => {
      const job = e.actor_kind === 'job';
      const failed = e.details?.result === 'failed' || (e.status ?? 0) >= 400;
      return {
        id: `audit:${e.id}`,
        at: e.created_at as string,
        kind: job ? 'run' : 'change',
        module: auditModule(e.action),
        title: e.action,
        detail: job ? String(e.details?.result ?? 'ran') : [e.actor_kind, e.actor_id].filter(Boolean).join(' ') || e.source,
        tone: failed ? 'bad' : 'ok',
        link: 'activity?tab=changes',
      };
    });
}

export function fromKnowledgeRuns(runs: KnowledgeRun[]): TimelineRow[] {
  return runs.map((r) => ({
    id: `knowledge:${r.id}`,
    at: r.started_at,
    kind: 'run',
    module: 'knowledge',
    title: `${r.kind === 'upload' ? 'Upload' : 'Crawl'} ${r.source_key}`,
    detail: r.error ?? (r.changed ? `${r.chunks ?? 0} passages` : 'unchanged'),
    tone: r.error ? 'bad' : 'ok',
    link: 'activity?tab=knowledge',
  }));
}

const POST_MODULES: Record<Delivery['source'], string> = { event: 'alerts', feed: 'feeds', leetcode: 'leetcode', test: 'alerts' };

// Messages that Platform posted: feed items, LeetCode posts, events and tests.
export function fromDeliveries(list: Delivery[]): TimelineRow[] {
  return list
    .filter((d) => d.created_at)
    .map((d) => ({
      id: `delivery:${d.id}`,
      at: d.created_at as string,
      kind: 'post',
      module: POST_MODULES[d.source] ?? 'alerts',
      title: d.title,
      detail: d.error ?? undefined,
      tone: d.status === 'failed' ? 'bad' : 'ok',
      link: d.message_url ? undefined : 'alerts',
      href: d.message_url ?? undefined,
    }));
}

export function fromCi(repos: CiRepo[]): TimelineRow[] {
  return repos.flatMap((r) =>
    r.runs
      .filter((run) => run.started_at)
      .map((run, i) => ({
        id: `ci:${r.repo}:${i}`,
        at: run.started_at as string,
        kind: 'ci' as const,
        module: 'ci',
        title: `${r.repo}: ${run.title ?? run.workflow ?? 'run'}`,
        detail: [run.workflow, run.branch].filter(Boolean).join(' · ') || undefined,
        tone: runTone(run.status, run.conclusion),
        href: run.url ?? undefined,
      })),
  );
}

// Every row, newest first. The sources write times in more than one ISO form, so rows sort by the parsed time.
export function mergeTimeline(...lists: TimelineRow[][]): TimelineRow[] {
  const time = (row: TimelineRow) => Date.parse(row.at) || 0;
  return lists.flat().sort((a, b) => time(b) - time(a) || a.id.localeCompare(b.id));
}
