import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

import { applyGroundedConversationFocus } from '../lib/conversationFocus.ts';
import { parseWorldConsequence } from '../lib/worldConsequence.ts';

const home = {
  id: 'home-1', conversation_id: 'conversation-1',
  provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
  lng: 103.920730, lat: 30.753792,
};

test('grounded Conversation consequence uses the existing manual Focus callback after reread', () => {
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

  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  assert.match(page, /applyGroundedConversationFocus\(\s*pendingFocus\.propertyId, currentConversationId, durableProperties, focusChoice/);
  assert.match(page, /onClick=\{\(event\) => \{\s*event\.stopPropagation\(\);\s*focusChoice\(property\.id\)/);
});

test('stream transport preserves Subject Focus and existing Property Focus', () => {
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
  });
  assert.deepEqual(parseWorldConsequence({ focus_property_id: 'property-1' }), {
    focusPropertyId: 'property-1',
    focusSubject: undefined,
  });
  assert.deepEqual(parseWorldConsequence(true), {});
});
