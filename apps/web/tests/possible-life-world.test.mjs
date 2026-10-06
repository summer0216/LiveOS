import assert from 'node:assert/strict';
import test from 'node:test';

import {
  resolvePossibleLifeProjectionFocus,
  resolvePossibleLifeWorld,
} from '../lib/possibleLifeWorld.ts';

const work = {
  identity: '融科资讯中心',
  geographic_identity: '北京市海淀区融科资讯中心',
  geographic_precision: 'PLACE', geographic_status: 'GROUNDED',
  lng: 116.326178, lat: 39.984098, relationship: 'WORK',
};

function possibleLife(id, residenceId, minutes) {
  return {
    id,
    work_subject_owner_id: 'owner-1',
    residence_property_id: residenceId,
    living_time_residence_property_id: residenceId,
    personal_meaning_reference: 'living_profile.commute_minutes',
    work_subject: work,
    living_time: {
      residence_property_id: residenceId,
      residence_identity: residenceId,
      residence_geographic_identity: `北京市海淀区${residenceId}`,
      work_subject_identity: work.identity,
      work_geographic_identity: work.geographic_identity,
      travel_minutes: minutes,
      travel_mode: 'PUBLIC_TRANSIT',
      evidence_source: 'AMAP_DIRECTION_API',
      evidence_reference: 'amap-route',
    },
    personal_meaning: {
      reference: 'living_profile.commute_minutes',
      maximum_commute_minutes: 30,
      satisfied: true,
    },
  };
}

test('Possible Life identity resolves authoritative World references for projection', () => {
  const residences = [
    { id: 'home-1', geographic_status: 'GROUNDED', lng: 116.28, lat: 39.98 },
    { id: 'home-2', geographic_status: 'GROUNDED', lng: 116.29, lat: 39.99 },
  ];
  const lives = [possibleLife('life-1', 'home-1', 20), possibleLife('life-2', 'home-2', 25)];

  const projected = resolvePossibleLifeWorld(lives, residences);

  assert.deepEqual(projected.map(item => item.possibleLife.id), ['life-1', 'life-2']);
  assert.equal(projected[0].residence, residences[0]);
  assert.equal(projected[0].possibleLife.work_subject, work);
  assert.equal(projected[0].possibleLife.living_time.travel_minutes, 20);
  assert.equal(projected[0].possibleLife.personal_meaning.satisfied, true);

});

test('Property existence alone does not create a projected Possible Life', () => {
  const property = {
    id: 'property-only', geographic_status: 'GROUNDED', lng: 116.3, lat: 39.9,
  };
  assert.deepEqual(resolvePossibleLifeWorld([], [property]), []);
  assert.deepEqual(
    resolvePossibleLifeWorld([possibleLife('life-1', 'missing', 20)], [property]),
    [],
  );
});

test('Possible Life Focus foregrounds one authoritative projection without replacing World', () => {
  const residences = [
    { id: 'home-1', geographic_status: 'GROUNDED', lng: 116.28, lat: 39.98 },
    { id: 'home-2', geographic_status: 'GROUNDED', lng: 116.29, lat: 39.99 },
  ];
  const lives = [possibleLife('life-1', 'home-1', 20), possibleLife('life-2', 'home-2', 25)];
  const projected = resolvePossibleLifeWorld(lives, residences);
  const personalMeaning = {
    id: 'meaning-1',
    possible_life_id: 'life-1',
    meaning: '20分钟公共交通符合当前通勤约束。',
    living_time_residence_property_id: 'home-1',
    actual_travel_minutes: 20,
    actual_travel_mode: 'PUBLIC_TRANSIT',
    route_evidence_source: 'AMAP_DIRECTION_API',
    route_evidence_reference: 'amap-route',
    requirement_reference: 'living_profile.commute_minutes',
    maximum_commute_minutes: 30,
    requirement_satisfied: true,
  };
  const focus = {
    possible_life: {
      id: 'life-1',
      work_subject_owner_id: 'owner-1',
      residence_property_id: 'home-1',
      living_time_residence_property_id: 'home-1',
      personal_meaning_reference: 'living_profile.commute_minutes',
    },
    personal_meaning: personalMeaning,
  };

  const resolved = resolvePossibleLifeProjectionFocus(focus, projected);

  assert.equal(resolved.projectedPossibleLife, projected[0]);
  assert.equal(resolved.projectedPossibleLife.possibleLife, lives[0]);
  assert.equal(resolved.personalMeaning, personalMeaning);
  assert.deepEqual(projected.map(item => item.possibleLife.id), ['life-1', 'life-2']);
  assert.equal(projected[1].possibleLife, lives[1]);
  assert.equal(resolvePossibleLifeProjectionFocus({
    ...focus,
    possible_life: { ...focus.possible_life, residence_property_id: 'home-2' },
  }, projected), null);

});
