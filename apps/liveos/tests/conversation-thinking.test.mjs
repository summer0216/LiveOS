import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');
const cache = new Map();
function load(url) {
  if (cache.has(url.href)) return cache.get(url.href);
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(url, 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const localRequire = (name) => {
    if (name === 'react') return { ...React, useEffect() {}, useRef: () => ({ current: null }) };
    if (name === 'next/image') return { __esModule: true, default: ({ alt, src }) => React.createElement('img', { alt, src }) };
    if (name.endsWith('.css')) return { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) };
    // Profile fetching is outside this presentation check.
    if (name === './UnderstandingSummary') return { __esModule: true, default: () => null };
    if (name === '../../infrastructure/conversationApi') return { setMessageFeedback: async () => ({ feedback: null }) };
    if (name.startsWith('.')) return load(new URL(`${name}${name === './markdown' ? '.ts' : '.tsx'}`, url));
    return require(name);
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`, { filename: fileURLToPath(url) })(localRequire, compiled, compiled.exports);
  cache.set(url.href, compiled.exports);
  return compiled.exports;
}
const Transcript = load(new URL('../features/first-conversation/ConversationTranscript.tsx', import.meta.url)).default;
const user = { id: 'u', role: 'user', content: '你好' };
const assistant = (id, content) => ({ id, role: 'assistant', content });
const render = (messages, isResponding) => renderToStaticMarkup(React.createElement(Transcript, { messages, isResponding }));

test('pending assistant uses its existing identity and three accessible thinking dots', () => {
  const html = render([user, assistant('a', '')], true);
  assert.ok(html.includes('assistant thinkingMessage'));
  assert.equal((html.match(/aria-label="LiveOS 正在思考"/g) ?? []).length, 1);
  assert.equal((html.match(/aria-hidden="true"/g) ?? []).length, 3);
  assert.equal((html.match(/alt="LiveOS"/g) ?? []).length, 1);
  assert.equal((html.match(/<article/g) ?? []).length, 2);
});

test('first response text replaces thinking within the same message unit', () => {
  const html = render([user, assistant('a', '你好，我是 LiveOS。')], true);
  assert.ok(html.includes('你好，我是 LiveOS。'));
  assert.ok(!html.includes('LiveOS 正在思考'));
  assert.ok(!html.includes('thinkingMessage'));
  assert.equal((html.match(/alt="LiveOS"/g) ?? []).length, 1);
  assert.equal((html.match(/<article/g) ?? []).length, 2);
});

test('only the active empty assistant thinks; stopped and restored turns do not', () => {
  assert.equal((render([assistant('old', ''), user, assistant('a', '  ')], true).match(/LiveOS 正在思考/g) ?? []).length, 1);
  assert.ok(!render([user, assistant('a', '')], false).includes('LiveOS 正在思考'));
  assert.ok(!render([user], true).includes('LiveOS 正在思考'));
});

test('only persisted AI messages display local HH:mm and preserve the server datetime', () => {
  const userTime = '2026-10-17T07:43:47.941053Z';
  const aiTime = '2026-10-17T07:44:04.729396Z';
  const messages = [{ ...user, created_at: userTime }, { ...assistant('a', '收到。'), created_at: aiTime }];
  const html = render(messages, false);
  const format = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  assert.ok(!html.includes(`dateTime="${userTime}"`));
  assert.ok(html.includes(`dateTime="${aiTime}">${format.format(new Date(aiTime))}</time>`));
  assert.equal((html.match(/<time /g) ?? []).length, 1);
  assert.equal(render(messages, false), html);
});

test('local streaming messages and invalid timestamps never fabricate a displayed time', () => {
  assert.ok(!render([user, assistant('a', '')], true).includes('<time '));
  assert.ok(!render([user, assistant('a', '首段正文')], true).includes('<time '));
  assert.ok(!render([{ ...assistant('a', '正文'), created_at: 'invalid' }], false).includes('<time '));
});

test('feedback belongs only to persisted assistant replies, never user or local streaming messages', () => {
  const html = renderToStaticMarkup(React.createElement(Transcript, {
    conversationId: 'cid', isResponding: false,
    messages: [
      { ...user, created_at: '2026-10-17T07:43:47Z' },
      { ...assistant('42', '已完成'), created_at: '2026-10-17T07:44:04Z', feedback: 'POSITIVE' },
      assistant('local:assistant', '尚未持久化'),
    ],
  }));
  assert.equal((html.match(/aria-label="回复评价"/g) ?? []).length, 1);
  assert.ok(html.includes('aria-label="赞同回复" aria-pressed="true"'));
});

test('copy shares the AI message actions with feedback and timestamp, without adding user actions', () => {
  const html = renderToStaticMarkup(React.createElement(Transcript, {
    conversationId: 'cid', isResponding: false,
    messages: [
      { ...user, created_at: '2026-10-17T07:43:47Z' },
      { ...assistant('42', '完整回复'), created_at: '2026-10-17T07:44:04Z', feedback: 'POSITIVE' },
    ],
  }));
  const articles = html.match(/<article\b[\s\S]*?<\/article>/g);
  assert.doesNotMatch(articles[0], /复制回复|回复评价/);
  assert.match(articles[1], /class="messageActions"/);
  assert.match(articles[1], /aria-label="复制回复"/);
  assert.match(articles[1], /aria-label="赞同回复" aria-pressed="true"/);
  assert.match(articles[1], /aria-label="不赞同回复" aria-pressed="false"/);
  assert.equal((articles[1].match(/<button /g) ?? []).length, 3);
  assert.equal((articles[1].match(/<time /g) ?? []).length, 1);
});
