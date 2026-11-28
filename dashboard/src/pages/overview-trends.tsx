import { useState } from 'react';
import { DailyBars } from '../components/charts';
import { Card, CardHeader, cx, ErrorNote, Segmented, Skeleton } from '../components/ui';
import { compact } from '../lib/format';
import { useTrends } from '../lib/queries';

const RANGES = [7, 30, 90] as const;

// The last chart fills the rest of its row, so the grid shows no empty cell at 2 or 3 columns.
const SM_FILL = ['', 'sm:col-span-2'];
const LG_FILL = ['lg:col-span-1', 'lg:col-span-3', 'lg:col-span-2'];
function fillRow(count: number) {
  return cx(SM_FILL[count % 2], LG_FILL[count % 3]);
}

// Daily charts of what happened in the org: actions, jobs, points, orders, knowledge and alerts.
export function TrendsCard({ prefix }: { prefix: string }) {
  const [days, setDays] = useState<(typeof RANGES)[number]>(30);
  const { data, isLoading, error } = useTrends(prefix, days);

  return (
    <Card className="mt-6">
      <CardHeader
        title="Activity over time"
        hint="Per day, UTC"
        action={
          <Segmented label="Range" value={days} onChange={setDays} options={RANGES.map((n) => ({ value: n, label: `${n}d` }))} />
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
          {data.series.map((s, i) => (
            <div key={s.key} className={cx('bg-panel p-4', i === data.series.length - 1 && fillRow(data.series.length))}>
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
