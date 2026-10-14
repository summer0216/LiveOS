import assert from 'node:assert/strict';
import test from 'node:test';
import { markdownBlocks, inlineTokens, safeMarkdownHref } from '../features/first-conversation/markdown.ts';

test('responses retain headings, paragraphs, lists and quoted context', () => {
  const blocks = markdownBlocks('## 下一步\n\n先了解预算。\n\n1. 预算\n2. 通勤\n\n- 生活方式\n\n> 尚待确认');
  assert.deepEqual(blocks.map((block) => block.kind), ['heading', 'paragraph', 'list', 'list', 'quote']);
  assert.equal(blocks[2].ordered, true);
  assert.deepEqual(blocks[2].items, ['预算', '通勤']);
  assert.equal(blocks[3].ordered, false);
});

test('links reject script, data and protocol-relative destinations; HTML remains text', () => {
  for (const href of ['javascript:alert(1)', 'data:text/html,x', '//evil.example']) assert.equal(safeMarkdownHref(href), null);
  assert.equal(safeMarkdownHref('https://example.com'), 'https://example.com');
  const tokens = inlineTokens('**重点**、*说明*、`代码`和[来源](https://example.com)');
  assert.deepEqual(tokens.filter((token) => token.kind !== 'text').map((token) => token.kind), ['strong', 'em', 'code', 'link']);
  assert.deepEqual(inlineTokens('<img src=x onerror=alert(1)>'), [{ kind: 'text', text: '<img src=x onerror=alert(1)>' }]);
});

test('an incomplete streamed code fence keeps its text without dropping chunks', () => {
  assert.deepEqual(markdownBlocks('```txt\n未完成\n仍在流式回复'), [{ kind: 'code', text: '未完成\n仍在流式回复' }]);
});

test('response dividers render as rules rather than literal Markdown punctuation', () => {
  assert.deepEqual(markdownBlocks('说明\n---\n下一步').map((block) => block.kind), ['paragraph', 'rule', 'paragraph']);
});
