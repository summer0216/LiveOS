import assert from 'node:assert/strict';
import test from 'node:test';
import { selectEnvironmentProjection } from '../features/living-world/selectEnvironmentProjection.ts';

const place = { propertyId: 'home', conversationId: 'conversation', identity: '已确认住所', center: { lng: 104, lat: 30 } };
function fixture() {
  const admission = { status: 'ADMITTED', property_id: 'home', property_identity: place.identity,
    property_lng: 104, property_lat: 30, evidence_reference: 'https://example.com/evidence', evidence_observed_at: '2026-10-24T00:00:00Z' };
  const sources = Array.from({ length: 20 }, (_, index) => {
    const tram = index < 3;
    const id = `provider-${index}`;
    const identity = `真实候选-${index}`;
    return { structure_version: 3, external_id: id, name: identity, identity, category: 'TRANSIT', type_code: tram ? '150705' : '150700',
      lng: 104 + index / 1000, lat: 30.001, distance_m: 350 + index, walking_minutes: 5,
      evidence: { source_record_id: id, identity, source_provider: 'AMAP', source_reference: admission.evidence_reference, observed_at: admission.evidence_observed_at }, admission: { ...admission } };
  });
  const property = { id: 'home', conversation_id: 'conversation', geographic_status: 'GROUNDED', geographic_identity: place.identity, lng: 104, lat: 30, place_context: sources };
  const eligibility = { conversation_id: 'conversation', source_user_turn_id: 12, items: sources.slice(0, 3).map((source) => ({
    attention: { conversation_id: 'conversation', source_user_turn_id: 12, property_id: 'home', property_identity: place.identity,
      property_lng: 104, property_lat: 30, category: 'TRANSIT', type_codes: ['150500'] },
    environment_external_id: source.external_id, environment_identity: source.identity, environment_type_code: source.type_code,
    evidence: { ...source.evidence }, admission: { ...admission }, relevance_basis: 'RELATED_RAIL_SUPPLEMENT',
  })) };
  return { property, eligibility };
}
test('projects only qualified coordinates, preserving three Tram supplements and excluding seventeen Bus', () => {
  const { property, eligibility } = fixture();
  const result = selectEnvironmentProjection(place, [property], eligibility);
  assert.equal(result.length, 3);
  assert.ok(result.every((item) => item.typeCode === '150705' && item.relevance === 'RELATED_RAIL_SUPPLEMENT'));
  assert.equal(result[0].walkingMinutes, null); // A POI estimate is not walking evidence.
  assert.deepEqual(result[1].center, { lng: 104.001, lat: 30.001 });
  assert.equal(selectEnvironmentProjection(place, [property], null).length, 0);
});
test('cross-place, cross-turn, mismatched evidence, missing admission and invalid coordinates never project', () => {
  for (const mutate of [
    (f) => { f.eligibility.conversation_id = 'another'; },
    (f) => { f.eligibility.items.forEach((i) => { i.attention.source_user_turn_id = 11; }); },
    (f) => { f.eligibility.items.forEach((i) => { i.attention.property_id = 'other'; }); },
    (f) => { f.property.place_context.forEach((s) => { s.evidence.source_reference = 'different'; }); },
    (f) => { f.property.place_context.forEach((s) => { s.admission.status = 'REJECTED'; }); },
    (f) => { f.property.place_context.forEach((s) => { s.lng = NaN; }); },
  ]) {
    const f = fixture(); mutate(f);
    assert.equal(selectEnvironmentProjection(place, [f.property], f.eligibility).length, 0);
  }
});
test('direct and supplement retain independent identity and relevance; duplicate eligibility does not duplicate markers', () => {
  const { property, eligibility } = fixture();
  property.place_context[0].type_code = eligibility.items[0].environment_type_code = '150500';
  eligibility.items[0].relevance_basis = 'USER_EXPRESSED_CATEGORY';
  eligibility.items.push(eligibility.items[0]);
  const result = selectEnvironmentProjection(place, [property], eligibility);
  assert.equal(result.length, 3);
  assert.equal(result[0].relevance, 'USER_EXPRESSED_CATEGORY');
  assert.equal(result[1].relevance, 'RELATED_RAIL_SUPPLEMENT');
});
