import assert from 'node:assert/strict';
import test from 'node:test';
import { rentBudgetMeaning } from '../lib/rentBudgetMeaning.ts';

test('budget meaning is exact and deterministic', () => {
  assert.equal(rentBudgetMeaning(6800, 6000), '超出预算 ¥800');
  assert.equal(rentBudgetMeaning(5800, 6000), '低于预算 ¥200');
  assert.equal(rentBudgetMeaning(6000, 6000), '符合预算');
});
