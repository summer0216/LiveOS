import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const ts = require('typescript');
function load(path, dependencies) {
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(
    (name) => dependencies[name] ?? require(name), compiled, compiled.exports,
  );
  return compiled.exports;
}
const contract = load('../../web/lib/environmentEligibility.ts', {});
const consequence = load('../../web/lib/worldConsequence.ts', { './environmentEligibility.ts': contract });
const empty = { conversation_id: 'cid', source_user_turn_id: 42, items: [] };
const item = {
  attention: { ...empty, source_quote: '附近有地铁吗', property_id: 'home', property_identity: '住宅',
    property_lng: 116, property_lat: 39, category: 'TRANSIT', type_codes: ['150500'], place_binding_source: 'FOCUS' },
  environment_external_id: 'station', environment_identity: '真实地铁站',
  environment_type_code: '150500',
  evidence: { source_provider: 'AMAP', source_reference: 'provider', source_record_id: 'station',
    identity: '真实地铁站', observed_at: '2026-10-20T00:00:00Z' },
  admission: { status: 'ADMITTED', admitted_at: '2026-10-20T00:00:00Z', property_id: 'home',
    property_identity: '住宅', property_lng: 116, property_lat: 39, evidence_reference: 'provider',
    evidence_observed_at: '2026-10-20T00:00:00Z', authority: 'PLACE_CONTEXT_REALITY_ADMISSION' },
  relevance_basis: 'USER_EXPRESSED_CATEGORY',
};

test('SSE forwards populated and empty eligibility without losing Focus or AI chunks', async () => {
  const full = { ...empty, items: [item] };
  const supplements = { ...empty, items: [0, 1, 2].map((i) => ({ ...item,
    environment_external_id: `tram-${i}`, environment_type_code: '150705',
    relevance_basis: 'RELATED_RAIL_SUPPLEMENT',
  })) };
  const received = [], chunks = [];
  const wire = [
    `event: world-consequence-ready\ndata: ${JSON.stringify({ focus_property_id: 'home', environment_eligibility: full })}\n\n`,
    `event: world-consequence-ready\ndata: ${JSON.stringify({ environment_eligibility: empty })}\n\n`,
    `event: world-consequence-ready\ndata: ${JSON.stringify({ environment_eligibility: supplements })}\n\n`,
    'data: "正常回复"\n\n',
  ].join('');
  const { streamMessage } = load('../../web/services/chat.ts', {
    '@/lib/worldConsequence': consequence,
    './api': { apiRequest: async () => new Response(wire) },
  });
  await streamMessage({ conversationId: 'cid', message: '附近有地铁吗',
    onChunk: (chunk) => chunks.push(chunk),
    onWorldConsequenceReady: (...values) => received.push(values),
  });
  assert.equal(received[0][0], 'home');
  assert.deepEqual(received.map((values) => values[3]), [full, empty, supplements]);
  assert.deepEqual(chunks, ['正常回复']);
  assert.notEqual(consequence.parseWorldConsequence(true), null);
  assert.equal(consequence.parseWorldConsequence({ focus_property_id: 'home' }).focusPropertyId, 'home');
});

test('transport rejects malformed, cross-turn and missing-evidence eligibility', () => {
  for (const invalid of [
    { ...empty, source_user_turn_id: null },
    { ...empty, items: [{ ...item, evidence: null }] },
    { ...empty, items: [{ ...item, attention: { ...item.attention, source_user_turn_id: 43 } }] },
    { ...empty, items: [{ ...item, attention: { ...item.attention, conversation_id: 'other' } }] },
  ]) assert.equal(consequence.parseWorldConsequence({ environment_eligibility: invalid }), null);
});
