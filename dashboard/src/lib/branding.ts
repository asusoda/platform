// Org branding: validation that mirrors the API, and the accent color applied as CSS variables.

import { useEffect } from 'react';

export const DARK_TEXT = '#000000';
export const LIGHT_TEXT = '#ffffff';

export function isHexColor(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

export function isHttpsUrl(value: string): boolean {
  if (!value || /\s/.test(value) || value.length > 500) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function channel(hex: string, offset: number): number {
  const c = parseInt(hex.slice(offset, offset + 2), 16) / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

// WCAG relative luminance of a #RRGGBB color.
export function luminance(hex: string): number {
  return 0.2126 * channel(hex, 1) + 0.7152 * channel(hex, 3) + 0.0722 * channel(hex, 5);
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// The text color, near black or white, with the higher contrast on the given background.
export function readableForeground(hex: string): string {
  return contrast(hex, DARK_TEXT) >= contrast(hex, LIGHT_TEXT) ? DARK_TEXT : LIGHT_TEXT;
}

// Sets --accent and --accent-fg on the document root while color is a valid hex; otherwise the theme defaults apply.
export function useAccentColor(color: string | null | undefined) {
  useEffect(() => {
    const root = document.documentElement.style;
    if (!color || !isHexColor(color)) return;
    root.setProperty('--accent', color);
    root.setProperty('--accent-fg', readableForeground(color));
    return () => {
      root.removeProperty('--accent');
      root.removeProperty('--accent-fg');
    };
  }, [color]);
}
