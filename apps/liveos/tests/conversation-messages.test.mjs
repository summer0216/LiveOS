import assert from 'node:assert/strict';
import test from 'node:test';
import {
  appendAssistantChunk,
  restoreConversationMessages,
} from '../runtime/conversationMessages.ts';

test('history recovery preserves role and order while assigning stable conversation scoped keys', () => {
  const messages = restoreConversationMessages('conversation-1', [
    { role: 'user', content: '你是谁？' },
    { role: 'assistant', content: '我是 LiveOS。' },
  ]);
  assert.deepEqual(messages.map(({ id, role, content }) => [id, role, content]), [
    ['conversation-1:0', 'user', '你是谁？'],
    ['conversation-1:1', 'assistant', '我是 LiveOS。'],
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
