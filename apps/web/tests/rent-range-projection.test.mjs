import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const propertyService = readFileSync(new URL('../services/property.ts', import.meta.url), 'utf8');

test('controlled rent estimate is projected as an approximate range, not confirmed rent', () => {
  assert.match(propertyService, /rent_estimate_kind: 'CONTROLLED_ESTIMATE' \| null/);
  assert.match(page, /预计租金 ¥\{property\.estimated_rent_min\.toLocaleString\('zh-CN'\)\}–\{property\.estimated_rent_max\.toLocaleString\('zh-CN'\)\} \/ 月/);
  assert.match(page, /实际租金仍需确认/);
  assert.match(page, /估计范围 · 非已确认租金/);
});
