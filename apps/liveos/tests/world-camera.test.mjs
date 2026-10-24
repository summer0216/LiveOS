import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import test from 'node:test';

const require = createRequire(import.meta.url);
const React = require('react');
const ts = require('typescript');

function harness() {
  const slots = [];
  let cursor = 0;
  let effects = [];
  const memo = (value, deps) => {
    const index = cursor++;
    const previous = slots[index];
    const changed = !previous || deps.some((item, i) => item !== previous.deps[i]);
    if (changed) slots[index] = { value, deps };
    return { value: slots[index].value, changed };
  };
  const hooks = {
    ...React,
    useRef(value) { const index = cursor++; return slots[index] ??= { current: value }; },
    useState(value) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = value;
      return [slots[index], (next) => { slots[index] = next; }];
    },
    useCallback(value, deps) { return memo(value, deps).value; },
    useLayoutEffect(fn, deps) { if (memo(fn, deps).changed) fn(); },
    useEffect(fn, deps) { if (memo(fn, deps).changed) effects.push(fn); },
  };
  const compiled = { exports: {} };
  const code = ts.transpileModule(readFileSync(new URL('../features/living-world/WorldEmergence.tsx', import.meta.url), 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`)((name) => {
    if (name === 'react') return hooks;
    if (name.endsWith('.css')) return { default: new Proxy({}, { get: (_, key) => key }) };
    if (name === './EnvironmentProjection') return { default: () => null };
    if (name === '@/features/living-map/AMapGround') return { default: () => null };
    return require(name);
  }, compiled, compiled.exports);
  return (place, animateAppearance, environment) => {
    cursor = 0;
    effects = [];
    const root = compiled.exports.default({ place, animateAppearance, environment });
    effects.forEach((fn) => fn());
    const [map, anchor, controls] = root.props.children;
    return { map: map.props, anchor: anchor.props, controls: controls.props.children, environment: root.props.children[3].props };
  };
}
const place = { identity: '已准入地点', name: '地点名称', center: { lng: 104, lat: 30 }, framing: { level: 'PLACE', attention: 'SEE' } };

test('marker waits for painted ground and projection; only a new live reveal opts into animation', () => {
  for (const animate of [false, true]) {
    const render = harness();
    const ui = render(place, animate);
    const node = { style: {}, dataset: {} };
    ui.anchor.ref.current = node;
    ui.map.onProjectionReady(() => ({ x: 240, y: 320 }));
    assert.equal(node.style.visibility, undefined);
    ui.map.onGroundReadyChange(true);
    assert.equal(node.style.visibility, 'visible');
    assert.equal(node.style.left, '240px');
    assert.equal(node.dataset.reveal, String(animate));
    render(place, true).map.onProjectionReady(() => ({ x: 260, y: 340 }));
    assert.equal(node.style.left, '260px');
    assert.equal(node.dataset.reveal, String(animate));
  }
});

test('ordinary rerenders retain AMap callbacks and do not request a camera move; controls reuse the camera contract', () => {
  const render = harness();
  const first = render(place, false);
  const calls = [];
  first.map.onCameraReady((...args) => calls.push(args));
  first.map.onZoomChange(15);
  first.map.onGroundReadyChange(true);
  const next = render({ ...place, center: { ...place.center }, framing: { ...place.framing } }, false);
  for (const callback of ['onProjectionReady', 'onCameraReady', 'onGroundReadyChange', 'onZoomChange']) {
    assert.equal(first.map[callback], next.map[callback]);
  }
  assert.equal(calls.length, 0);
  const anchor = { style: {}, dataset: {} };
  next.anchor.ref.current = anchor;
  next.controls[0].props.children[0].props.onClick();
  assert.deepEqual(calls[0], [place.center, 16, null, anchor]);
  next.controls[1].props.onClick();
  assert.deepEqual(calls[1], [place.center, place.framing]);
});

test('environment joins the existing map projection without remounting or moving its camera', () => {
  const render = harness();
  const first = render(place, false);
  const moves = [];
  first.map.onCameraReady((...args) => moves.push(args));
  first.map.onGroundReadyChange(true);
  const project = ({ lng, lat }) => ({ x: lng * 2, y: lat * 3 });
  first.map.onProjectionReady(project);
  const next = render(place, false, [{ id: 'tram', sourceUserTurnId: 12 }]);
  const received = [];
  next.environment.onProjectionListener((value) => received.push(value));
  assert.equal(received[0], project);
  const pan = () => ({ x: 80, y: 100 });
  next.map.onProjectionReady(pan);
  assert.equal(received[1], pan);
  assert.equal(first.map.onProjectionReady, next.map.onProjectionReady);
  assert.equal(moves.length, 0);
  next.environment.onProjectionListener(null);
  next.map.onProjectionReady(project);
  assert.equal(received.length, 2);
});
