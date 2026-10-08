import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { Logo } from '@/components/logo';
import { appName, repoUrl } from './shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <span className="inline-flex items-center gap-2 font-medium tracking-tight">
          <Logo className="size-5" />
          {appName}
        </span>
      ),
    },
    links: [{ text: 'Docs', url: '/docs', active: 'nested-url' }],
    githubUrl: repoUrl,
  };
}
