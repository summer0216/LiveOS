import assert from 'node:assert/strict';
import test from 'node:test';

import {
  decisionGeographyFingerprint,
  shouldApplyObservedDecisionGeography,
} from '../lib/decisionGeographyState.ts';

const grounded = (identity, lng, lat) => ({
  conversation_id: 'conversation-1',
  intent_established: true,
  intent_type: 'relocation',
  identity,
  identity_source: 'USER',
  geographic_scope: 'CITY',
  status: 'GROUNDED',
  lng,
  lat,
});

test('a newly persisted geography is observable before chat completion', () => {
  const previous = grounded('北京', 116.407387, 39.904179);
  const next = grounded('上海', 121.473667, 31.230525);

  assert.equal(
    shouldApplyObservedDecisionGeography({
      candidate: next,
      baselineFingerprint: decisionGeographyFingerprint(previous),
      observationId: 2,
      latestObservationId: 2,
    }),
    true,
  );
});

test('a late observation from an older turn cannot retake world ownership', () => {
  const previous = grounded('北京', 116.407387, 39.904179);
  const lateOlderTurn = grounded('新疆', 87.628579, 43.793301);

  assert.equal(
    shouldApplyObservedDecisionGeography({
      candidate: lateOlderTurn,
      baselineFingerprint: decisionGeographyFingerprint(previous),
      observationId: 2,
      latestObservationId: 3,
    }),
    false,
  );
});

test('the unchanged persisted state is not replayed as a new transition', () => {
  const current = grounded('北京', 116.407387, 39.904179);

  assert.equal(
    shouldApplyObservedDecisionGeography({
      candidate: current,
      baselineFingerprint: decisionGeographyFingerprint(current),
      observationId: 2,
      latestObservationId: 2,
    }),
    false,
  );
});
