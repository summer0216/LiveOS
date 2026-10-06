import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const propertyService = readFileSync(new URL('../services/property.ts', import.meta.url), 'utf8');

test('public evidence API capability remains without the retired root Action UI', () => {
  assert.match(propertyService, /\/properties\/\$\{encodeURIComponent\(propertyId\)\}\/public-rent-evidence/);
  assert.doesNotMatch(page, /handlePublicRentAction|executePublicRentAction|PUBLIC_EVIDENCE/);
});
