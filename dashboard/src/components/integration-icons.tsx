import { Brain, CalendarDays, Cloud, FileText, Flame, GraduationCap, Plug, Route, Search } from 'lucide-react';
import type { ComponentType } from 'react';
import { DiscordIcon, GitHubIcon } from './brand-icons';

// The icon of each integration key the API sends.
const ICONS: Record<string, ComponentType<{ className?: string }>> = {
  asu: GraduationCap,
  discord: DiscordIcon,
  github: GitHubIcon,
  google: CalendarDays,
  notion: FileText,
  runpod: Cloud,
  embeddings: Brain,
  firecrawl: Flame,
  openrouter: Route,
  searxng: Search,
};

export function IntegrationIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Plug;
  return <Icon className={className} />;
}
