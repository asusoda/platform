import Image from 'next/image';
import { Fragment } from 'react';
import { cn } from '@/lib/cn';
import { orgs as allOrgs, type Org } from '@/lib/orgs';

const sizes = { sm: 22, md: 32 } as const;

/** The org logos as overlapping circles, each a link with a tooltip. */
export function OrgMarks({
  orgs = allOrgs,
  size = 'md',
  className,
}: {
  orgs?: Org[];
  size?: keyof typeof sizes;
  className?: string;
}) {
  const px = sizes[size];
  return (
    <ul aria-label="Orgs that build Platform" className={cn('flex items-center', className)}>
      {orgs.map((org, i) => (
        <li key={org.url} className="relative hover:z-10 focus-within:z-10" style={{ marginLeft: i ? -px / 3 : 0 }}>
          <a
            href={org.url}
            aria-label={org.name}
            className="group relative block rounded-full ring-2 ring-fd-background transition-transform duration-150 ease-out outline-none hover:-translate-y-0.5 focus-visible:-translate-y-0.5 focus-visible:ring-fd-ring"
          >
            <span
              className="grid place-items-center overflow-hidden rounded-full border border-black/10 dark:border-white/15"
              style={{ width: px, height: px, background: org.background }}
            >
              <Image src={org.logo} alt="" width={px} height={px} className="size-[72%]" />
            </span>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 translate-y-1 rounded-md border bg-fd-popover px-2 py-1 text-xs whitespace-nowrap text-fd-popover-foreground opacity-0 shadow-md transition duration-150 ease-out group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100"
            >
              {org.name}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

/** "Built by A and B at ASU", with a link for each org. */
export function BuiltBy({ orgs = allOrgs, className }: { orgs?: Org[]; className?: string }) {
  return (
    <p className={className}>
      Built by{' '}
      {orgs.map((org, i) => (
        <Fragment key={org.url}>
          {i > 0 ? (i === orgs.length - 1 ? ' and ' : ', ') : null}
          <a
            href={org.url}
            className="font-medium text-fd-foreground underline decoration-fd-border underline-offset-4 transition-colors duration-150 ease-out hover:decoration-fd-foreground"
          >
            {org.short}
          </a>
        </Fragment>
      ))}{' '}
      at ASU
    </p>
  );
}
