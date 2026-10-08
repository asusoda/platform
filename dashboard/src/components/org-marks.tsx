import { BUILT_BY, type BuiltBy, builtByLabel } from '../lib/links';
import { Tooltip } from './tooltip';
import { cx } from './ui';

// The logos of the orgs that build Platform as a row of round marks. Each mark covers a third of the one before it.
// The ring has the color of the page background, so it shows a gap between two marks.
export function OrgMarks({
  orgs = BUILT_BY,
  size = 24,
  ring = 'ring-bg',
  className,
}: {
  orgs?: BuiltBy[];
  size?: number;
  ring?: string;
  className?: string;
}) {
  return (
    <div role="group" aria-label={builtByLabel(orgs)} className={cx('flex items-center', className)}>
      {orgs.map((org, i) => (
        <Tooltip key={org.name} label={org.name} side="top">
          <a
            href={org.url}
            target="_blank"
            rel="noreferrer"
            aria-label={org.name}
            style={{ width: size, height: size, marginLeft: i ? -Math.round(size / 3) : 0, zIndex: orgs.length - i }}
            className={cx(
              'relative block shrink-0 rounded-full ring-2 transition-transform duration-150 ease-out hover:z-10! hover:-translate-y-0.5',
              'after:absolute after:inset-0 after:rounded-full after:ring-1 after:ring-black/10 after:ring-inset',
              ring,
            )}
          >
            <img src={`${import.meta.env.BASE_URL}${org.logo}`} alt="" width={size} height={size} className="size-full rounded-full" />
          </a>
        </Tooltip>
      ))}
    </div>
  );
}
