import { describe, expect, it } from 'vitest';
import {
  CATEGORIES,
  INITIAL_FEEDBACK,
  PLATFORMS,
  SEVERITIES,
  TEXT_RULES,
  validateFeedback,
  type Feedback,
} from './feedback';

const valid: Feedback = {
  ...INITIAL_FEEDBACK,
  title: '射门后角色停顿',
  category: 'animation',
  build: '开发构建 / 分支 A',
  platform: 'windows',
  description: '射门结束后移动输入未立即生效。',
  actual: '角色短暂停顿。',
};

describe('validateFeedback', () => {
  it('accepts required fields without optional details or attachments', () => {
    expect(validateFeedback(valid)).toEqual({ valid: true, value: valid });
  });

  it('keeps unselected categories and platforms and default minor severity', () => {
    expect(INITIAL_FEEDBACK.category).toBe('');
    expect(INITIAL_FEEDBACK.platform).toBe('');
    expect(INITIAL_FEEDBACK.severity).toBe('minor');
    const validation = validateFeedback(INITIAL_FEEDBACK);
    expect(validation.valid).toBe(false);
    if (validation.valid) return;
    expect(Object.keys(validation.errors).sort()).toEqual(['title', 'category', 'build', 'platform', 'description', 'actual'].sort());
  });

  for (const key of ['title', 'build', 'description', 'actual'] as const) {
    it(`rejects whitespace-only ${key}`, () => {
      const validation = validateFeedback({ ...valid, [key]: ' \n\t ' });
      expect(validation.valid).toBe(false);
      if (!validation.valid) expect(validation.errors[key]).toBeDefined();
    });
  }

  for (const key of Object.keys(TEXT_RULES) as (keyof typeof TEXT_RULES)[]) {
    it(`accepts maximum length and rejects overflow for ${key}`, () => {
      expect(validateFeedback({ ...valid, [key]: '测'.repeat(TEXT_RULES[key].max) }).valid).toBe(true);
      const overflow = validateFeedback({ ...valid, [key]: '测'.repeat(TEXT_RULES[key].max + 1) });
      expect(overflow.valid).toBe(false);
      if (!overflow.valid) expect(overflow.errors[key]).toContain(String(TEXT_RULES[key].max));
    });
  }

  it('measures trimmed values without changing inputs or line breaks', () => {
    const feedback = { ...valid, title: `  ${'字'.repeat(120)}  `, stepsText: '  第一行\n第二行  ', expected: ' \n ' };
    const original = structuredClone(feedback);
    expect(validateFeedback(feedback).valid).toBe(true);
    expect(feedback).toEqual(original);
  });

  it('accepts all stable categories, severities and platforms', () => {
    for (const category of CATEGORIES) {
      for (const severity of SEVERITIES) {
        for (const platform of PLATFORMS) {
          expect(validateFeedback({ ...valid, category: category.value, severity: severity.value, platform: platform.value }).valid).toBe(true);
        }
      }
    }
  });

  it('rejects invalid runtime enum values', () => {
    const feedback = { ...valid, category: 'invalid', severity: 'invalid', platform: 'invalid' } as unknown as Feedback;
    const validation = validateFeedback(feedback);
    expect(validation.valid).toBe(false);
    if (!validation.valid) expect(Object.keys(validation.errors).sort()).toEqual(['category', 'platform', 'severity']);
  });
});
