import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';
const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');

test('eligible markers follow geographic projection; detail closes back to the same marker', () => {
  const values = []; let cursor = 0, listener;
  const hooks = { ...React,
    useRef(initial) { const i = cursor++; return values[i] ??= { current: initial }; },
    useState(initial) { const i = cursor++; if (!(i in values)) values[i] = initial; return [values[i], (v) => { values[i] = v; }]; },
    useCallback(fn) { return fn; }, useLayoutEffect(fn) { fn(); },
  };
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL('../features/living-world/EnvironmentProjection.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)((name) => {
    if (name === 'react') return hooks;
    if (name.endsWith('.css')) return { default: {} };
    if (name === './EnvironmentDetail') return { default: () => null, environmentDistance: () => '' };
    return require(name);
  }, compiled, compiled.exports);
  const items = [{ id: 'tram', name: '真实电车站', category: 'TRANSIT', relevance: 'RELATED_RAIL_SUPPLEMENT', center: { lng: 104, lat: 30 } }];
  const render = (ready = true) => { cursor = 0; return compiled.exports.default({ items, ready, onProjectionListener: (v) => { listener = v; } }); };
  assert.equal(render(false).props.hidden, true);
  const button = render().props.children[0][0];
  const node = { style: {}, focus() { this.focused = true; } };
  button.props.ref(node);
  listener(({ lng, lat }) => ({ x: lng * 2, y: lat * 3 }));
  assert.deepEqual(node.style, { left: '208px', top: '90px', visibility: 'visible' });
  listener(() => ({ x: 75, y: 80 }));
  assert.equal(node.style.left, '75px');
  button.props.onClick();
  const detail = render().props.children[1];
  assert.equal(detail.props.item, items[0]);
  detail.props.onClose();
  assert.equal(node.focused, true);
  assert.equal(render().props.children[1], undefined);
});
