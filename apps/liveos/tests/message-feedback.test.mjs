import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

function harness(feedback = null, send = async (_cid, message_id, value) => ({ message_id, feedback: value })) {
  const slots = [];
  let cursor = 0;
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL('../features/first-conversation/MessageFeedback.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const localRequire = (name) => {
    if (name === 'react') return {
      useEffect() {},
      useState(value) { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], (next) => { slots[i] = next; }]; },
      useRef(value) { const i = cursor++; return slots[i] ??= { current: value }; },
    };
    if (name.endsWith('.css')) return { __esModule: true, default: {} };
    if (name.endsWith('/conversationApi')) return { setMessageFeedback: send };
    return require(name);
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)(localRequire, compiled, compiled.exports);
  const render = () => { cursor = 0; return compiled.exports.default({ conversationId: 'cid', messageId: '42', feedback }); };
  return {
    html: () => renderToStaticMarkup(render()),
    click: (index) => render().props.children[0].props.children[index].props.onClick(),
  };
}

test('feedback creates, changes and cancels the selected value on the same persisted message', async () => {
  const calls = [];
  const ui = harness(null, async (cid, id, feedback) => { calls.push([cid, id, feedback]); return { feedback }; });
  assert.equal((ui.html().match(/aria-pressed="false"/g) ?? []).length, 2);
  await ui.click(0);
  assert.match(ui.html(), /aria-label="赞同回复" aria-pressed="true"/);
  await ui.click(1);
  assert.match(ui.html(), /aria-label="不赞同回复" aria-pressed="true"/);
  await ui.click(1);
  assert.equal((ui.html().match(/aria-pressed="false"/g) ?? []).length, 2);
  assert.deepEqual(calls, [['cid', '42', 'POSITIVE'], ['cid', '42', 'NEGATIVE'], ['cid', '42', null]]);
  assert.match(harness('NEGATIVE').html(), /aria-label="不赞同回复" aria-pressed="true"/);
});

test('pending feedback blocks duplicate requests; failure restores previous selection and announces error', async () => {
  let reject;
  let calls = 0;
  const ui = harness('POSITIVE', () => { calls++; return new Promise((_resolve, fail) => { reject = fail; }); });
  const pending = ui.click(1);
  assert.match(ui.html(), /aria-busy="true"/);
  assert.equal((ui.html().match(/disabled=""/g) ?? []).length, 2);
  await ui.click(0);
  assert.equal(calls, 1);
  reject(new Error('network unavailable'));
  await pending;
  assert.match(ui.html(), /aria-label="赞同回复" aria-pressed="true"/);
  assert.match(ui.html(), /role="alert">评价未保存，请重试。/);
  assert.match(ui.html(), /aria-busy="false"/);
});
