import { describe, expect, it } from 'vitest';
import { displayValue, titleCase } from '../utils/formatters';
import { formatDate } from '../utils/dateUtils';

describe('formatters', () => {
  it('displays fallback for empty values', () => {
    expect(displayValue(null)).toBe('Not available');
    expect(displayValue('Sarah')).toBe('Sarah');
  });

  it('title cases snake case', () => {
    expect(titleCase('affiliation_update')).toBe('Affiliation Update');
  });

  it('formats dates', () => {
    expect(formatDate('2026-09-02')).toBe('2026-09-02');
    expect(formatDate(null)).toBe('Unknown');
  });
});
