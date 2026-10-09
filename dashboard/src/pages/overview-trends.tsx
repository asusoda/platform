import { useState } from 'react';
import { DailyBars } from '../components/charts';
import { Card, CardHeader, cx, ErrorNote, Skeleton } from '../components/ui';
import { compact } from '../lib/format';
import { useTrends } from '../lib/queries';

const RANGES = [7, 30, 90] as const;

// Daily charts of what happened in the org: actions, jobs, points, orders, agent questions, knowledge and alerts.
export function TrendsCard({ prefix }: { prefix: string }) {
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const { data, isLoading, error } = useTrends(prefix, days);

  return (
    <Card className="mt-6">
      <CardHeader
        title="Activity over time"
        hint="One bar per day, in UTC"
        action={
          <div role="group" aria-label="Range" className="flex rounded-md border border-line p-0.5">
            {RANGES.map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={days === n}
                onClick={() => setDays(n)}
                className={cx(
                  'h-6 cursor-pointer rounded px-2 text-xs transition-colors',
                  days === n ? 'bg-panel-2 text-fg' : 'text-muted hover:text-fg',
                )}
              >
                {n}d
              </button>
            ))}
          </div>
        }
      />
      {error ? (
        <div className="p-4">
          <ErrorNote error={error} />
        </div>
      ) : isLoading || !data ? (
        <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-3 bg-panel p-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-18 w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
          {data.series.map((s) => (
            <div key={s.key} className="bg-panel p-4">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-muted">{s.title}</span>
                {s.failed ? <span className="text-xs text-bad">{compact(s.failed)} failed</span> : null}
              </div>
              <div className="mt-1 mb-3 text-xl font-semibold tabular-nums">
                {compact(s.total)} <span className="text-xs font-normal text-muted">{s.unit}</span>
              </div>
              <DailyBars days={s.days} unit={s.unit} label={s.title} />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
