import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  admittedPlaceContextFor,
  groundedPlaceContextScope,
  hasCompleteAdmittedPlaceContext,
  reconcileRereadPlaceContext,
  requestPlaceContextOnce,
} from '../features/first-reality-runtime/placeContext.ts';

const runtime = readFileSync(
  new URL('../features/first-reality-runtime/index.ts', import.meta.url),
  'utf8',
);

const home = {
  id: 'home-1',
  conversation_id: 'conversation-1',
  provenance: 'USER_PROVIDED',
  geographic_status: 'GROUNDED',
  geographic_identity: 'current grounded place',
  lng: 104,
  lat: 31,
  place_context: null,
};
const nearby = {
  structure_version: 3,
  external_id: 'place-1',
  evidence: { source_provider: 'AMAP', source_reference: 'place/around' },
  admission: {
    status: 'ADMITTED',
    property_id: home.id,
    property_identity: home.geographic_identity,
    property_lng: home.lng,
    property_lat: home.lat,
  },
};

test('only the current grounded Property can trigger Place Context', () => {
  assert.ok(groundedPlaceContextScope(home.conversation_id, home));
  assert.equal(groundedPlaceContextScope('another-conversation', home), null);
  assert.equal(groundedPlaceContextScope(home.conversation_id, {
    ...home, geographic_status: 'UNRESOLVED',
  }), null);
  assert.equal(groundedPlaceContextScope(home.conversation_id, {
    ...home, provenance: 'AMAP_RESIDENTIAL_POI',
  }), null);
  assert.match(runtime, /if \(!placeContextScope \|\| !placeContextPropertyId \|\| hasCompletePlaceContext\) return;/);
  assert.match(runtime, /establishPlaceContext\(conversationId, placeContextPropertyId\)\s*\.then\(\(\) => getProperties\(conversationId\)\)/);
});

test('only persisted admission bound to the current Property is exposed', () => {
  const persisted = {
    ...home,
    place_context: [
      { ...nearby, structure_version: 2, admission: undefined },
      { ...nearby, admission: { ...nearby.admission, property_id: 'old-home' } },
      nearby,
    ],
  };
  assert.deepEqual(admittedPlaceContextFor(persisted), [nearby]);
  assert.equal(hasCompleteAdmittedPlaceContext(persisted), false);
  assert.equal(hasCompleteAdmittedPlaceContext({ ...home, place_context: [nearby] }), true);
  assert.match(runtime, /admittedPlaceContextReality,/);
});

test('acquisition is shared once, then authoritative reread survives reconciliation', async () => {
  const scope = groundedPlaceContextScope(home.conversation_id, home);
  assert.ok(scope);
  const attempts = new Map();
  let acquisitions = 0;
  const persisted = { ...home, place_context: [nearby] };
  const acquireAndReread = async () => {
    acquisitions += 1;
    return [persisted];
  };
  const first = requestPlaceContextOnce(attempts, scope, acquireAndReread);
  const second = requestPlaceContextOnce(attempts, scope, acquireAndReread);
  assert.strictEqual(first, second);
  assert.deepEqual(await first, [persisted]);
  await requestPlaceContextOnce(attempts, scope, acquireAndReread);
  assert.equal(acquisitions, 1);

  const newerConversationState = [{ ...home, rent: 6000 }];
  const reconciled = reconcileRereadPlaceContext(
    newerConversationState, persisted, home.conversation_id, scope,
  );
  assert.equal(reconciled[0].rent, 6000);
  assert.deepEqual(admittedPlaceContextFor(reconciled[0]), [nearby]);
  assert.equal(hasCompleteAdmittedPlaceContext(reconciled[0]), true);
  assert.strictEqual(reconcileRereadPlaceContext(
    newerConversationState,
    { ...persisted, lng: 105 },
    home.conversation_id,
    scope,
  ), newerConversationState);
});
