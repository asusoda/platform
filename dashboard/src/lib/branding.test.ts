import { describe, expect, it } from 'vitest';
import { DARK_TEXT, LIGHT_TEXT, contrast, isHexColor, isHttpsUrl, readableForeground } from './branding';

describe('branding validation', () => {
  it('accepts only #RRGGBB colors', () => {
    expect(isHexColor('#1f6FEB')).toBe(true);
    expect(isHexColor('#fff')).toBe(false);
    expect(isHexColor('red')).toBe(false);
    expect(isHexColor('#12345g')).toBe(false);
  });

  it('accepts only https logo URLs', () => {
    expect(isHttpsUrl('https://cdn.example.org/logo.png')).toBe(true);
    expect(isHttpsUrl('http://cdn.example.org/logo.png')).toBe(false);
    expect(isHttpsUrl('javascript:alert(1)')).toBe(false);
    expect(isHttpsUrl('https://example.org/a b.png')).toBe(false);
    expect(isHttpsUrl('')).toBe(false);
  });
});

describe('readableForeground', () => {
  it('picks the text color with more contrast', () => {
    expect(readableForeground('#ffcc00')).toBe(DARK_TEXT);
    expect(readableForeground('#1e3a8a')).toBe(LIGHT_TEXT);
    expect(readableForeground('#000000')).toBe(LIGHT_TEXT);
    expect(readableForeground('#ffffff')).toBe(DARK_TEXT);
  });

  it('meets 4.5:1 for every grey', () => {
    for (let v = 0; v <= 255; v += 5) {
      const hex = `#${v.toString(16).padStart(2, '0').repeat(3)}`;
      expect(contrast(hex, readableForeground(hex))).toBeGreaterThanOrEqual(4.5);
    }
  });
});
