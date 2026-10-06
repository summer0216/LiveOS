import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const propertyService = readFileSync(new URL('../services/property.ts', import.meta.url), 'utf8');

test('controlled rent estimate capability remains while its retired root presentation is absent', () => {
  assert.match(propertyService, /rent_estimate_kind: 'CONTROLLED_ESTIMATE' \| null/);
  assert.doesNotMatch(page, /estimated_rent_min|实际租金仍需确认|估计范围/);
});
