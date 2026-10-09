// The Platform mark, the same as the one on the site.
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <rect x="3" y="15" width="18" height="5" rx="1.5" fill="currentColor" />
      <rect x="3" y="9" width="18" height="4" rx="1.5" fill="currentColor" opacity="0.55" />
      <rect x="3" y="4" width="18" height="3" rx="1.5" fill="currentColor" opacity="0.25" />
    </svg>
  );
}
