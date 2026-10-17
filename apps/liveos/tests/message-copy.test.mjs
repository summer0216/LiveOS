import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

function harness(content, writeText = async () => {}) {
  const slots = [], timers = new Map();
  let cursor = 0, cleanup, effectInstalled = false, timerId = 0;
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL('../features/first-conversation/MessageCopy.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const localRequire = (name) => {
    if (name === 'react') return {
      useEffect(effect) { if (!effectInstalled) { effectInstalled = true; cleanup = effect(); } },
      useState(value) { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], (next) => { slots[i] = next; }]; },
      useRef(value) { const i = cursor++; return slots[i] ??= { current: value }; },
    };
    if (name.endsWith('.css')) return { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) };
    return require(name);
  };
  vm.runInThisContext(`(function(require,module,exports,navigator,setTimeout,clearTimeout){${code}\n})`)(
    localRequire, compiled, compiled.exports, { clipboard: { writeText } },
    (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; },
    (id) => timers.delete(id),
  );
  const render = () => { cursor = 0; return compiled.exports.default({ content }); };
  return {
    html: () => renderToStaticMarkup(render()),
    click: () => render().props.children[0].props.onClick(),
    expire() { const queued = [...timers.values()]; timers.clear(); queued.forEach(({ callback }) => callback()); },
    timers,
    unmount: () => cleanup(),
  };
}

test('copy writes the full raw AI content verbatim and briefly replaces Copy with Check', async () => {
  const raw = '  ## 原始回复\n\n**预算**：6000 元\n- 第一项\n- 第二项\n```text\n代码\n```\n';
  const clipboard = [];
  const ui = harness(raw, async (text) => { clipboard.push(text); });
  assert.match(ui.html(), /lucide-copy/);
  await ui.click();
  assert.deepEqual(clipboard, [raw]);
  assert.match(ui.html(), /lucide-check/);
  assert.match(ui.html(), /aria-label="已复制"/);
  assert.equal([...ui.timers.values()][0].ms, 2000);
  ui.expire();
  assert.match(ui.html(), /lucide-copy/);
  assert.match(ui.html(), /aria-label="复制回复"/);
});

test('clipboard rejection announces failure without a false Check or reset timer', async () => {
  const ui = harness('回复', async () => { throw new Error('denied'); });
  await ui.click();
  assert.match(ui.html(), /lucide-copy/);
  assert.doesNotMatch(ui.html(), /lucide-check/);
  assert.match(ui.html(), /role="status">复制失败，请重试。/);
  assert.equal(ui.timers.size, 0);
});

test('repeated copies reuse one reset timer; unmount clears it and ignores late completion', async () => {
  const ui = harness('回复');
  await ui.click();
  await ui.click();
  assert.equal(ui.timers.size, 1);
  ui.unmount();
  assert.equal(ui.timers.size, 0);
  let complete;
  const pending = harness('回复', () => new Promise((resolve) => { complete = resolve; }));
  const copying = pending.click();
  pending.unmount();
  complete();
  await copying;
  assert.equal(pending.timers.size, 0);
});
