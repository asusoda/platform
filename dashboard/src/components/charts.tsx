import { useId, useState } from 'react';
import { compact } from '../lib/format';
import type { TrendDay } from '../lib/types';

const WIDTH = 300;
const HEIGHT = 72;
const GAP = 2;

function dayLabel(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

// Bars of one value per day. The failed part of a day is drawn in red on top of the rest.
// Hover or focus shows the day and its value in place of the axis labels.
export function DailyBars({ days, unit, label }: { days: TrendDay[]; unit: string; label: string }) {
  const [active, setActive] = useState<number | null>(null);
  const id = useId();
  const max = Math.max(1, ...days.map((d) => d.value));
  const step = WIDTH / Math.max(1, days.length);
  const bar = Math.max(1, step - GAP);
  const shown = active === null ? null : days[active];
  const total = days.reduce((sum, d) => sum + d.value, 0);

  return (
    <div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="block h-18 w-full"
        role="img"
        aria-labelledby={`${id}-label`}
        onMouseLeave={() => setActive(null)}
      >
        <title id={`${id}-label`}>{`${label}: ${compact(total)} ${unit} in ${days.length} days`}</title>
        <line x1="0" x2={WIDTH} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} className="stroke-line" strokeWidth="1" />
        {days.map((d, i) => {
          const h = d.value ? Math.max(2, (d.value / max) * (HEIGHT - 4)) : 0;
          const bad = d.value ? (d.failed / d.value) * h : 0;
          const x = i * step + GAP / 2;
          const dim = active !== null && active !== i;
          return (
            <g key={d.date} onMouseEnter={() => setActive(i)} className={dim ? 'opacity-40' : undefined}>
              <rect x={i * step} y="0" width={step} height={HEIGHT} fill="transparent" />
              {h ? (
                <rect x={x} y={HEIGHT - h} width={bar} height={h - bad} rx="1" className="fill-accent" />
              ) : null}
              {bad ? <rect x={x} y={HEIGHT - bad} width={bar} height={bad} rx="1" className="fill-bad" /> : null}
            </g>
          );
        })}
      </svg>
      <div className="mt-1.5 flex h-4 items-center justify-between text-[11px] text-muted tabular-nums">
        {shown ? (
          <span className="text-fg">
            {dayLabel(shown.date)}: {compact(shown.value)} {unit}
            {shown.failed ? <span className="text-bad"> ({compact(shown.failed)} failed)</span> : null}
          </span>
        ) : (
          <>
            <span>{days.length ? dayLabel(days[0].date) : ''}</span>
            <span>Today</span>
          </>
        )}
      </div>
    </div>
  );
}
