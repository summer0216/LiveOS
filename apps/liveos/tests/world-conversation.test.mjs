import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');

function harness(width = 390) {
  const slots = [];
  let cursor = 0;
  let expanded = false;
  const hooks = {
    ...React,
    useEffect() {},
    useRef(value) { const index = cursor++; return slots[index] ??= { current: value }; },
    useState(value) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = value;
      return [slots[index], (next) => { slots[index] = next; }];
    },
  };
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL('../features/living-world/WorldConversation.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInNewContext(`(function(require,module,exports){${code}\n})`, {
    window: { matchMedia: () => ({ matches: width >= 1024 }) },
  })((name) => {
    if (name === 'react') return hooks;
    if (name.endsWith('.css')) return { default: new Proxy({}, { get: (_, key) => key }) };
    return require(name);
  }, compiled, compiled.exports);
  const conversation = React.createElement('div', null, '真实消息');
  const entry = React.createElement('footer', null, '共享 Composer');
  const render = () => {
    cursor = 0;
    const root = compiled.exports.default({ context: '实际地点', isResponding: false, expanded,
      onExpandedChange(value) { expanded = value; }, conversation, entry });
    const [dock, panel] = root.props.children;
    const [handle, header, body, footer] = panel.props.children;
    return { root, dock, panel, handle, close: header.props.children[1], body, footer };
  };
  return { render, conversation, entry };
}
const pointer = (clientY) => ({ clientY, pointerId: 1, currentTarget: { setPointerCapture() {} } });
const swipe = (element, from, to) => {
  element.props.onPointerDown(pointer(from));
  element.props.onPointerUp(pointer(to));
};

test('dock and panel are mutually exclusive; Esc and close return the same dock without replacing content', () => {
  const h = harness(1280);
  let ui = h.render();
  assert.equal(ui.dock.props.hidden, false);
  assert.equal(ui.panel.props.hidden, true);
  ui.dock.props.onClick();
  ui = h.render();
  assert.equal(ui.dock.props.hidden, true);
  assert.equal(ui.panel.props.hidden, false);
  assert.equal(ui.body.props.children, h.conversation);
  assert.equal(ui.footer.props.children, h.entry);
  ui.panel.props.onKeyDown({ key: 'Escape', stopPropagation() {} });
  ui = h.render();
  assert.equal(ui.dock.props.hidden, false);
  assert.equal(ui.panel.props.hidden, true);
  assert.equal(ui.footer.props.children, h.entry);
  ui.dock.props.onClick();
  h.render().close.props.onClick();
  assert.equal(h.render().panel.props.hidden, true);
});

for (const width of [390, 834]) {
  test(`${width}px dock and handle swipes traverse collapsed, expanded, full screen and back`, () => {
    const h = harness(width);
    let ui = h.render();
    swipe(ui.dock, 600, 500);
    ui = h.render();
    assert.equal(ui.panel.props.hidden, false);
    assert.equal(ui.root.props['data-full-screen'], false);
    swipe(ui.handle, 400, 300);
    ui.handle.props.onClick();
    ui = h.render();
    assert.equal(ui.root.props['data-full-screen'], true);
    swipe(ui.handle, 50, 150);
    ui = h.render();
    assert.equal(ui.root.props['data-full-screen'], false);
    assert.equal(ui.panel.props.hidden, false);
    swipe(ui.handle, 300, 400);
    ui = h.render();
    assert.equal(ui.panel.props.hidden, true);
    assert.equal(ui.dock.props.hidden, false);
    assert.equal(ui.footer.props.children, h.entry);
  });
}

test('desktop ignores sheet gestures and small movements do not collapse the conversation', () => {
  const desktop = harness(1440);
  swipe(desktop.render().dock, 600, 400);
  assert.equal(desktop.render().panel.props.hidden, true);
  const mobile = harness();
  mobile.render().dock.props.onClick();
  swipe(mobile.render().handle, 400, 420);
  assert.equal(mobile.render().panel.props.hidden, false);
});
