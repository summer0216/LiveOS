import assert from 'node:assert/strict';
import test from 'node:test';
import {
  appendAssistantChunk,
  restoreConversationMessages,
} from '../runtime/conversationMessages.ts';

test('history recovery preserves persisted identity, timestamp, role and order', () => {
  const messages = restoreConversationMessages([
    { id: '101', created_at: '2026-10-17T00:00:00Z', role: 'user', content: '你是谁？' },
    { id: '102', created_at: '2026-10-17T00:00:02Z', role: 'assistant', content: '我是 LiveOS。' },
  ]);
  assert.deepEqual(messages.map(({ id, created_at, role, content }) => [id, created_at, role, content]), [
    ['101', '2026-10-17T00:00:00Z', 'user', '你是谁？'],
    ['102', '2026-10-17T00:00:02Z', 'assistant', '我是 LiveOS。'],
  ]);
});

test('SSE chunks append only to their active assistant turn', () => {
  const messages = [
    { id: 'turn:1:user', role: 'user', content: '你是谁？' },
    { id: 'turn:1:assistant', role: 'assistant', content: '我是' },
  ];
  assert.deepEqual(appendAssistantChunk(messages, 'turn:1:assistant', ' LiveOS。'), [
    messages[0],
    { ...messages[1], content: '我是 LiveOS。' },
  ]);
  assert.deepEqual(appendAssistantChunk(messages, 'stale-turn', '过期内容'), messages);
});

test('history recovery preserves feedback alongside message identity', () => {
  const history = [{ id: '102', created_at: '2026-10-17T00:00:02Z', role: 'assistant', content: '回复', feedback: 'NEGATIVE' }];
  assert.equal(restoreConversationMessages(history)[0].feedback, 'NEGATIVE');
  assert.equal(restoreConversationMessages([{ ...history[0], feedback: null }])[0].feedback, null);
});
