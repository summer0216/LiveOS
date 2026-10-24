import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';
import { isEnvironmentEligibilityResult } from '../../web/lib/environmentEligibility.ts';
import { appendAssistantChunk, restoreConversationMessages } from '../runtime/conversationMessages.ts';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = ts.transpileModule(readFileSync(new URL('../runtime/useConversationSession.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const persisted = [
  { id: '9007199254740993', created_at: '2026-10-17T01:00:00Z', role: 'user', content: '测试' },
  { id: '9007199254740994', created_at: '2026-10-17T01:00:01Z', role: 'assistant', content: '第一段第二段' },
];

// Exercise the actual hook with controlled API promises and a minimal hook lifecycle.
function session({ initialId = '', history, stream }) {
  const values = [], effects = [];
  let cursor = 0;
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!(index in values)) values[index] = typeof initial === 'function' ? initial() : initial;
      return [values[index], (next) => { values[index] = typeof next === 'function' ? next(values[index]) : next; }];
    },
    useRef(initial) {
      const index = cursor++;
      return values[index] ??= { current: initial };
    },
    useCallback(callback) { return callback; },
    useEffect(effect) { if (!effects.length) effects.push(effect); },
  };
  const compiled = { exports: {} };
  vm.runInNewContext(`(function(require,module,exports){${source}\n})`, {
    URL, Error, window: { location: { href: 'http://localhost:3002/' }, history: { replaceState() {} } },
  })((name) => {
    if (name === 'react') return react;
    if (name === '../../web/lib/environmentEligibility') return { isEnvironmentEligibilityResult };
    if (name === '@/lib/createClientId') return { createClientId: () => 'conversation-1' };
    if (name === '../infrastructure/conversationApi') return { getConversationHistory: history, streamMessage: stream };
    if (name === './conversationMessages') return { appendAssistantChunk, restoreConversationMessages };
    throw new Error(`Unexpected dependency ${name}`);
  }, compiled, compiled.exports);
  return {
    read() { cursor = 0; return compiled.exports.useConversationSession(initialId); },
    mount() { effects[0](); },
  };
}

test('stream uses temporary identity then reconciles once to server history; refresh is identical', async () => {
  let client, historyCalls = 0;
  client = session({
    history: async (id) => { assert.equal(id, 'conversation-1'); historyCalls++; return { messages: persisted }; },
    stream: async ({ onChunk }) => {
      onChunk('第一段');
      const pending = client.read();
      assert.equal(pending.messages[1].id, '1:assistant');
      assert.equal(pending.messages[1].created_at, undefined);
      assert.equal(pending.messages[1].content, '第一段');
      onChunk('第二段');
      assert.equal(client.read().messages[1].content, '第一段第二段');
    },
  });
  await client.read().submit('测试');
  const completed = client.read();
  assert.deepEqual(completed.messages, persisted);
  assert.equal(completed.isResponding, false);
  assert.equal(historyCalls, 1);
  const refresh = session({ initialId: 'conversation-1', history: async () => ({ messages: persisted }) });
  refresh.read(); refresh.mount();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(refresh.read().messages, completed.messages);
});

test('failed metadata recovery preserves streamed messages and exposes an error', async () => {
  const client = session({
    history: async () => { throw new Error('History unavailable'); },
    stream: async ({ onChunk }) => { onChunk('完整回复'); },
  });
  await client.read().submit('测试');
  assert.deepEqual(Array.from(client.read().messages, (item) => item.content), ['测试', '完整回复']);
  assert.equal(client.read().error, 'History unavailable');
  assert.equal(client.read().isResponding, false);
});

test('world consequences refresh Reality before EOF without interrupting chunks or history reconciliation', async () => {
  let emit, finish;
  const stream = new Promise((resolve) => { finish = resolve; });
  let historyCalls = 0, refreshes = 0;
  const client = session({
    history: async (id) => { assert.equal(id, 'conversation-1'); historyCalls++; return { messages: persisted }; },
    stream: (options) => { emit = options; return stream; },
  });
  const pending = client.read().submit('测试', () => { refreshes++; });
  assert.equal(emit.onWorldStateReady, undefined); // Early Geography is not Property admission.
  emit.onWorldConsequenceReady();
  assert.equal(refreshes, 1);
  assert.equal(client.read().isResponding, true);
  assert.equal(historyCalls, 0);
  emit.onChunk('第一段');
  emit.onWorldConsequenceReady();
  emit.onChunk('第二段');
  assert.equal(client.read().messages[1].content, '第一段第二段');
  assert.equal(client.read().conversationId, 'conversation-1');
  finish();
  await pending;
  assert.deepEqual(client.read().messages, persisted);
  assert.equal(client.read().isResponding, false);
  assert.equal(historyCalls, 1);
});

test('session forwards turn-bound eligibility and ignores another conversation', async () => {
  const empty = { conversation_id: 'conversation-1', source_user_turn_id: 42, items: [] };
  const received = [];
  const client = session({
    history: async () => ({ messages: persisted }),
    stream: async ({ onWorldConsequenceReady, onChunk }) => {
      onWorldConsequenceReady(undefined, undefined, undefined, empty);
      onWorldConsequenceReady(undefined, undefined, undefined, { ...empty, conversation_id: 'other' });
      onChunk('正常回复');
    },
  });
  await client.read().submit('这里附近有地铁吗？', (value) => received.push(value));
  assert.deepEqual(received, [empty]);
  assert.equal(client.read().environmentEligibility, empty);
  assert.deepEqual(client.read().messages, persisted);
});

test('new expression clears prior eligibility while awaiting its own authoritative result', async () => {
  let client, count = 0;
  const eligible = { conversation_id: 'conversation-1', source_user_turn_id: 42, items: [] };
  client = session({ history: async () => ({ messages: persisted }),
    stream: async ({ onWorldConsequenceReady }) => {
      assert.equal(client.read().environmentEligibility, null);
      if (++count === 1) onWorldConsequenceReady(undefined, undefined, undefined, eligible);
    },
  });
  await client.read().submit('first');
  assert.equal(client.read().environmentEligibility, eligible);
  await client.read().submit('next');
  assert.equal(client.read().environmentEligibility, null);
});


test('resume restores valid history eligibility and rejects another conversation or malformed qualification', async () => {
  const eligibility = { conversation_id: 'saved', source_user_turn_id: 42, items: [] };
  for (const payload of [eligibility, { ...eligibility, conversation_id: 'other' }, { items: [] }, null]) {
    const client = session({ initialId: 'saved', history: async () => ({ messages: persisted, environment_eligibility: payload }) });
    client.read(); client.mount();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(client.read().environmentEligibility, payload === eligibility ? eligibility : null);
    assert.deepEqual(client.read().messages, persisted);
    assert.equal(client.read().isRestoring, false);
  }
});
