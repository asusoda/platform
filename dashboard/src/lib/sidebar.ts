// The collapsed state of the sidebar, kept in localStorage. Ctrl+B, Cmd+B or [ changes it.

import { useCallback, useEffect, useState } from 'react';

const KEY = 'platform.sidebar';

function stored(): boolean {
  try {
    return localStorage.getItem(KEY) === 'collapsed';
  } catch {
    return false;
  }
}

// True when the key event comes from a field where the officer types text.
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

export function useSidebarCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(stored);
  const toggle = useCallback(() => setCollapsed((c) => !c), []);

  useEffect(() => {
    try {
      if (collapsed) localStorage.setItem(KEY, 'collapsed');
      else localStorage.removeItem(KEY);
    } catch {
      // Storage blocked: the state lasts until the tab closes
    }
  }, [collapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.altKey || e.shiftKey) return;
      const mod = e.ctrlKey || e.metaKey;
      const bracket = e.key === '[' && !mod && !typing(e.target);
      if ((mod && e.key.toLowerCase() === 'b') || bracket) {
        if (document.querySelector('dialog[open]')) return;
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggle]);

  return [collapsed, toggle];
}
