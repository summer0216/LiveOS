import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
const propertyService = readFileSync(new URL('../services/property.ts', import.meta.url), 'utf8');

test('focused persisted user rent Action executes without an Unknown', () => {
  assert.match(page, /const userInitiatedPublicRentAction = singleFocused\s+&& !property\.meaningful_unknown\s+&& property\.reality_action_type === 'PUBLIC_EVIDENCE'\s+&& Boolean\(property\.reality_action_label\)/);
  assert.match(page, /!singleFocusedHome\.meaningful_unknown\s+&& singleFocusedHome\.reality_action_type === 'PUBLIC_EVIDENCE'\s+&& singleFocusedHome\.reality_action_label/);
  assert.match(page, /onClick=\{\(\) => \{ void handlePublicRentAction\(singleFocusedHome\.id\); \}\}/);
  assert.match(page, /const result = await executePublicRentAction\(conversationId, propertyId\)/);
  assert.match(propertyService, /\/properties\/\$\{encodeURIComponent\(propertyId\)\}\/public-rent-evidence/);
});

test('user rent Action bypasses the local toggle while decision-driven Action remains rendered', () => {
  assert.match(page, /singleFocused && property\.rent === null && !userInitiatedPublicRentAction/);
  assert.match(page, /\{singleFocusedHome\.meaningful_unknown && \([\s\S]*?singleFocusedHome\.reality_action_type === 'PUBLIC_EVIDENCE'[\s\S]*?handlePublicRentAction\(singleFocusedHome\.id\)/);
});
