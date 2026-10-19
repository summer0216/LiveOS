import assert from 'node:assert/strict';
import test from 'node:test';
import { selectGroundedPlace } from '../features/living-world/groundedPlace.ts';

const place = (overrides = {}) => ({
  conversation_id: 'conversation-1',
  provenance: 'USER_PROVIDED',
  decision_state: 'ACTIVE',
  title: '龙湖时代天街',
  geographic_identity: '成都龙湖时代天街',
  geographic_precision: 'PLACE',
  geographic_status: 'GROUNDED',
  lng: 104.03,
  lat: 30.7,
  ...overrides,
});

test('only the active conversation grounded place with identity and verified coordinates emerges', () => {
  const selected = selectGroundedPlace('conversation-1', [
    place({ geographic_status: 'UNRESOLVED' }),
    place({ provenance: 'AMAP_RESIDENTIAL_POI' }),
    place({ decision_state: 'REJECTED' }),
    place({ lng: null }),
    place(),
  ]);
  assert.equal(selected?.identity, '成都龙湖时代天街');
  assert.equal(selected?.name, '龙湖时代天街');
  assert.deepEqual(selected?.center, { lng: 104.03, lat: 30.7 });
  assert.deepEqual(selected?.framing, { level: 'PLACE', attention: 'SEE' });
  assert.equal(selectGroundedPlace('conversation-2', [place()]), null);
});

test('place label preserves the given name and never substitutes a full geographic address', () => {
  assert.equal(selectGroundedPlace('conversation-1', [place({ title: '  龙湖时代天街  ' })]).name, '龙湖时代天街');
  for (const title of [null, '', '   ']) {
    const selected = selectGroundedPlace('conversation-1', [place({ title })]);
    assert.equal(selected.name, null);
    assert.equal(selected.identity, '成都龙湖时代天街');
  }
});

test('no identity, precision or in-range grounded coordinates means no World', () => {
  for (const invalid of [
    { geographic_identity: null },
    { geographic_precision: null },
    { geographic_status: 'UNRESOLVED' },
    { lng: 181 },
    { lat: Number.NaN },
  ]) assert.equal(selectGroundedPlace('conversation-1', [place(invalid)]), null);
});
