import type { CatalogModule } from './types';

// Whether a module matches the search text, by its name, title, description, category, needs and packs.
export function matches(m: CatalogModule, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const text = [m.name, m.title, m.description, m.category, ...m.needs.map((n) => n.label), ...m.packs.map((p) => p.title)];
  return text.join(' ').toLowerCase().includes(q);
}
