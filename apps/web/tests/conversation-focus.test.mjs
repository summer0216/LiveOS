import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

import {
  applyGroundedConversationFocus,
  resolveWorkSubjectProjectionFocus,
} from '../lib/conversationFocus.ts';
import { parseWorldConsequence } from '../lib/worldConsequence.ts';

const home = {
  id: 'home-1', conversation_id: 'conversation-1',
  provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
  lng: 103.920730, lat: 30.753792,
};

test('grounded Conversation Focus capability remains available outside the retired root surface', () => {
  const focused = [];
  const focusChoice = (id) => focused.push(id);
  assert.equal(applyGroundedConversationFocus(
    undefined, 'conversation-1', [home], focusChoice,
  ), false);
  assert.equal(applyGroundedConversationFocus(
    'home-1', 'conversation-1', [home], focusChoice,
  ), true);
  assert.deepEqual(focused, ['home-1']);
  for (const invalid of [
    { ...home, conversation_id: 'other' },
    { ...home, geographic_status: 'UNRESOLVED' },
    { ...home, lng: null },
    { ...home, provenance: 'AMAP_RESIDENTIAL_POI' },
  ]) {
    assert.equal(applyGroundedConversationFocus(
      'home-1', 'conversation-1', [invalid], focusChoice,
    ), false);
  }
  assert.deepEqual(focused, ['home-1']);

});

test('stream transport preserves Possible Life, Subject, and Property Focus', () => {
  const subject = {
    identity: '融科资讯中心',
    geographic_identity: '北京市海淀区融科资讯中心',
    geographic_precision: 'PLACE',
    geographic_status: 'GROUNDED',
    lng: 116.326178,
    lat: 39.984098,
    relationship: 'WORK',
  };
  assert.deepEqual(parseWorldConsequence({ focus_subject: subject }), {
    focusPropertyId: undefined,
    focusSubject: subject,
    focusPossibleLife: undefined,
  });
  assert.deepEqual(parseWorldConsequence({ focus_property_id: 'property-1' }), {
    focusPropertyId: 'property-1',
    focusSubject: undefined,
    focusPossibleLife: undefined,
  });
  const possibleLifeFocus = {
    possible_life: {
      id: 'possible-life-1',
      work_subject_owner_id: 'owner-1',
      residence_property_id: 'property-1',
      living_time_residence_property_id: 'property-1',
      personal_meaning_reference: 'living_profile.commute_minutes',
    },
    personal_meaning: {
      id: 'meaning-1',
      possible_life_id: 'possible-life-1',
      meaning: '步行8分钟让日常安排保持从容。',
      living_time_residence_property_id: 'property-1',
      actual_travel_minutes: 8,
      actual_travel_mode: 'WALKING',
      route_evidence_source: 'AMAP_DIRECTION_API',
      route_evidence_reference: 'route-1',
      requirement_reference: 'living_profile.commute_minutes',
      maximum_commute_minutes: 30,
      requirement_satisfied: true,
    },
  };
  const parsedPossibleLife = parseWorldConsequence({
    focus_possible_life: possibleLifeFocus,
  });
  assert.deepEqual(parsedPossibleLife, {
    focusPropertyId: undefined,
    focusSubject: undefined,
    focusPossibleLife: possibleLifeFocus,
  });
  assert.equal(parsedPossibleLife.focusPossibleLife, possibleLifeFocus);
  assert.equal(parsedPossibleLife.focusPropertyId, undefined);
  assert.equal(parseWorldConsequence({
    focus_possible_life: {
      ...possibleLifeFocus,
      personal_meaning: {
        ...possibleLifeFocus.personal_meaning,
        possible_life_id: 'other-life',
      },
    },
  }), null);
  assert.deepEqual(parseWorldConsequence(true), {});

  const chatService = readFileSync(new URL('../services/chat.ts', import.meta.url), 'utf8');
  assert.match(chatService, /consequence\.focusPossibleLife/);
});

test('authoritative Work Subject projection capability remains reusable', () => {
  const subject = {
    identity: '融科资讯中心',
    geographic_identity: '北京市海淀区融科资讯中心',
    geographic_precision: 'PLACE',
    geographic_status: 'GROUNDED',
    lng: 116.326178,
    lat: 39.984098,
    relationship: 'WORK',
  };
  const profileWork = {
    work_location: '融科资讯中心',
    geographic_identity: '北京市海淀区融科资讯中心',
    geographic_precision: 'PLACE',
    geographic_status: 'GROUNDED',
    lng: 116.326178,
    lat: 39.984098,
  };
  const surroundingWorld = [home];

  assert.equal(resolveWorkSubjectProjectionFocus(subject, profileWork), subject);
  assert.deepEqual(surroundingWorld, [home]);
  assert.equal(resolveWorkSubjectProjectionFocus(
    { ...subject, identity: 'synthetic-work' }, profileWork,
  ), null);

});
