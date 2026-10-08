import { useState } from 'react';
import { cx } from './ui';

// The org's logo, or its first letter on the accent color when there is no logo or it fails to load.
export function OrgMark({ name, logoUrl, className }: { name: string; logoUrl?: string | null; className?: string }) {
  const [failed, setFailed] = useState<string | null>(null);
  const box = cx('flex shrink-0 items-center justify-center overflow-hidden rounded-md', className ?? 'size-6');
  if (logoUrl && failed !== logoUrl) {
    return (
      <span className={cx(box, 'bg-panel-2')}>
        <img
          src={logoUrl}
          alt=""
          referrerPolicy="no-referrer"
          className="size-full object-contain"
          onError={() => setFailed(logoUrl)}
        />
      </span>
    );
  }
  return (
    <span className={cx(box, 'bg-accent text-xs font-semibold text-accent-fg uppercase')} aria-hidden>
      {name.slice(0, 1)}
    </span>
  );
}
