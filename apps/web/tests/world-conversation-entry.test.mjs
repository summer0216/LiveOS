import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';
import * as placeContext from '../features/first-reality-runtime/placeContext.ts';
import * as scale from '../lib/geographicScaleContract.ts';

const require = createRequire(import.meta.url);
const tick = () => new Promise((resolve) => setImmediate(resolve));

// Exercise the production hook/component with controlled hooks and transport;
// timers, SSE completion and rerenders are explicit so no browser is required.
function hooks() {
  const slots = [];
  let cursor = 0;
  const effects = [];
  return {
    begin() { cursor = 0; },
    flush() { effects.splice(0).forEach((effect) => effect()); },
    useState(initial) {
      const slot = cursor++;
      if (!(slot in slots)) slots[slot] = typeof initial === 'function' ? initial() : initial;
      return [slots[slot], (value) => {
        slots[slot] = typeof value === 'function' ? value(slots[slot]) : value;
      }];
    },
    useRef(initial) {
      const slot = cursor++;
      if (!(slot in slots)) slots[slot] = { current: initial };
      return slots[slot];
    },
    useMemo(fn) { return fn(); },
    useCallback(fn) { return fn; },
    useEffect(fn, deps) {
      const slot = cursor++;
      const old = slots[slot];
      if (!old || deps.some((value, i) => !Object.is(value, old.deps[i]))) {
        const next = { deps, cleanup: null };
        slots[slot] = next;
        effects.push(() => { old?.cleanup?.(); next.cleanup = fn(); });
      }
    },
  };
}

function load(relativePath, dependencies, globals = {}) {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  const loaded = { exports: {} };
  runInNewContext(compiled, {
    module: loaded, exports: loaded.exports,
    require: (name) => name in dependencies ? dependencies[name] : require(name),
    console, ...globals,
    AbortController,
  });
  return loaded.exports.default;
}

function elements(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap((child) => elements(child, type));
  return [
    ...(tree.type === type ? [tree] : []),
    ...elements(tree.props?.children, type),
  ];
}

for (const outcome of ['ready', 'grounding-timeout', 'map-timeout', 'world-timeout']) {
test(`First Reality ${outcome}: direct reveal or bounded retry without SSE completion`, async () => {
  const react = hooks();
  const frames = [];
  const timers = new Map();
  const cameraCalls = [];
  const home = {
    id: 'home', conversation_id: 'fresh', title: '当前住所',
    provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
    geographic_precision: 'PLACE', lng: 104, lat: 31,
  };
  let properties = [];
  let request;
  let complete;
  const Runtime = load('../features/first-reality-runtime/index.ts', {
    react, './placeContext': placeContext,
    '@/lib/createClientId': { createClientId: () => 'fresh' },
    '@/lib/geographicScaleContract': scale,
    '@/lib/decisionGeographyState': {
      isGroundedDecisionGeography: () => false, isCurrentExpressionReferent: () => false,
      decisionGeographyFingerprint: () => null, shouldApplyObservedDecisionGeography: () => false,
    },
    '@/services/chat': {
      getConversationHistory: async () => ({ messages: [] }),
      streamMessage: (options) => {
        request = options;
        return new Promise((resolve, reject) => {
          complete = resolve;
          options.signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
        });
      },
    },
    '@/services/profile': { getLivingProfile: async () => null },
    '@/services/property': {
      getProperties: async () => properties,
      establishPlaceContext: async () => {},
    },
    '@/services/decisionGeography': { getDecisionGeography: async () => null },
    '@/services/possibleLife': { getPossibleLives: async () => [] },
  }, {
    navigator: {},
    window: {
      setTimeout(fn, delay) { timers.set(delay, fn); return delay; },
      clearTimeout(id) { timers.delete(id); },
      requestAnimationFrame(fn) { frames.push(fn); return frames.length; },
      cancelAnimationFrame() {},
    },
    console: { ...console, info() {}, error() {} },
  });
  const render = () => { react.begin(); const result = Runtime({ initialConversationId: '' }); react.flush(); return result; };
  let runtime = render();
  runtime.onCameraReady((...args) => cameraCalls.push(args));
  const pending = runtime.submit('我住在当前住所');
  runtime = render();
  assert.equal(runtime.phase, 'forming');
  assert.equal(frames.length, 0, 'no admitted Reality means no reveal');
  if (outcome === 'grounding-timeout') {
    timers.get(90_000)();
    await pending;
    runtime = render();
    assert.equal(runtime.firstOpenStage, 'entry');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality, null);
    assert.equal(cameraCalls.length, 0);
    return;
  }
  properties = [home];
  request.onWorldStateReady('current-turn');
  await tick();
  runtime = render();
  assert.equal(runtime.phase, 'grounding');
  assert.equal(frames.length, 0, 'Grounding alone cannot reveal an unready map');
  if (outcome === 'map-timeout') {
    timers.get(90_000)();
    await pending;
    runtime = render();
    assert.equal(runtime.firstOpenStage, 'entry');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality.identity, home.title, 'timeout preserves admitted Reality');
    assert.equal(cameraCalls.length, 0);
    request.onWorldStateReady('stale-turn');
    complete();
    await tick();
    assert.equal(render().firstOpenStage, 'entry', 'late SSE cannot reveal the expired turn');
    return;
  }
  runtime.onGroundReadyChange(true);
  render();
  assert.equal(frames.length, 1, 'map readiness directly schedules the reveal');
  frames.shift()();
  runtime = render();
  assert.equal(runtime.firstOpenStage, 'world');
  assert.equal(timers.has(90_000), false, 'reveal ends the readiness deadline while SSE continues');
  assert.equal(cameraCalls.length, 1);
  assert.equal(JSON.stringify(cameraCalls[0][0]), JSON.stringify(runtime.authoritativeReality.center));
  if (outcome === 'world-timeout') {
    runtime.onWorldSettled();
    runtime = render();
    assert.equal(runtime.isSubmittingExpression, false, 'formed World releases the first request before SSE');
    const previousSignal = request.signal;
    const nextPending = runtime.submit('附近吃饭方便吗？');
    runtime = render();
    assert.equal(previousSignal.aborted, true, 'a newer Expression cancels the older stream');
    assert.equal(runtime.isSubmittingExpression, true);
    timers.get(90_000)();
    await Promise.all([pending, nextPending]);
    runtime = render();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.authoritativeReality.identity, home.title);
    assert.equal(runtime.isSubmittingExpression, false, 'World request timeout restores the entry');
    return;
  }
  complete();
  await pending;
});
}

test('one Expression Entry moves into World and accepts second and third expressions', async () => {
  const react = hooks();
  const timers = new Map();
  const submitted = [];
  let complete;
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: {
    setTimeout: (fn, delay) => { timers.set(delay, fn); return delay; },
    clearTimeout: (id) => timers.delete(id),
  } });
  let props = {
    stage: 'world', worldFormed: false, isSubmittingExpression: false,
    submittedExpression: '我住在当前住所', groundedIdentity: '当前住所',
    placeAnchorRef: { current: null }, map: 'same map', worldProjection: 'same anchor',
    onGroundingSettled() {},
    onWorldSettled() { props.worldFormed = true; },
    onSubmit(expression) {
      submitted.push(expression);
      return new Promise((resolve) => { complete = resolve; });
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  assert.equal(elements(tree, 'textarea').length, 1);
  assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  assert.equal(tree.props['data-world-entry'], true, 'entry is already at the bottom during reveal');
  assert.equal(elements(tree, 'textarea')[0].props.value, '');
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '后续表达草稿' } });
  tree = render();
  timers.get(3200)();
  tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.value, '后续表达草稿', 'World formation does not erase newly typed content');
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '' } });
  tree = render();
  assert.equal(tree.props['data-world-entry'], true);
  assert.equal(tree.props['data-frame'], 'world');
  for (const expression of ['附近吃饭方便吗？', '交通呢？']) {
    elements(tree, 'textarea')[0].props.onFocus();
    tree = render();
    assert.equal(tree.props['data-entry-frame'], 'focus');
    elements(tree, 'textarea')[0].props.onChange({ target: { value: expression } });
    tree = render();
    assert.equal(tree.props['data-entry-frame'], 'typing');
    const button = elements(tree, 'button')[0];
    assert.equal(button.props.disabled, false);
    assert.equal(button.props['aria-label'], '提交表达');
    button.props.onClick();
    // Repeated Enter in the same turn must not duplicate submission.
    elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
    props.isSubmittingExpression = true;
    tree = render();
    assert.equal(tree.props['data-frame'], 'world');
    assert.equal(tree.props['data-entry-frame'], 'transmitting');
    assert.equal(elements(tree, 'textarea')[0].props.readOnly, false, 'World can accept typing while the current turn finishes');
    assert.equal(elements(tree, 'textarea')[0].props.value, '', 'submission clears immediately');
    assert.equal(elements(tree, 'button')[0].props.disabled, true);
    complete();
    await tick();
    props.isSubmittingExpression = false;
    tree = render();
    assert.equal(elements(tree, 'textarea').length, 1);
    assert.equal(elements(tree, 'textarea')[0].props.value, '');
    assert.equal(tree.props['data-entry-frame'], 'ready');
    assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  }
  assert.deepEqual(submitted, ['附近吃饭方便吗？', '交通呢？']);
  assert.equal(timers.has(3200), false, 'formed World does not replay reveal');
});

test('World readiness releases the initial Entry lock before SSE; late completion cannot unlock a newer submit', async () => {
  const react = hooks();
  const requests = [];
  const completions = [];
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: { setTimeout: () => 1, clearTimeout() {} } });
  const props = {
    stage: 'entry', worldFormed: false, isSubmittingExpression: false,
    submittedExpression: null, groundedIdentity: null, placeAnchorRef: { current: null },
    onWorldSettled() {},
    onSubmit(expression) {
      requests.push(expression);
      return new Promise((resolve) => completions.push(resolve));
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '我住在当前住所' } });
  tree = render();
  elements(tree, 'button')[0].props.onClick();
  props.stage = 'world';
  props.worldFormed = true;
  tree = render(); // first SSE is still pending, but World is ready.
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '附近吃饭方便吗？' } });
  tree = render();
  elements(tree, 'button')[0].props.onClick();
  assert.deepEqual(requests, ['我住在当前住所', '附近吃饭方便吗？']);
  props.isSubmittingExpression = true;
  tree = render();
  completions[0]();
  await tick();
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '交通呢？' } });
  tree = render();
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.equal(requests.length, 2, 'old SSE completion does not release a newer pending turn');
  props.isSubmittingExpression = false;
  tree = render(); // current turn semantic reconciliation completes, SSE still pending.
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.equal(requests.length, 3, 'next Expression does not wait for reply SSE completion');
  completions[1]();
  completions[2]();
  await tick();
});

test('First Open click and Enter share submission and block a duplicate in-flight turn', async () => {
  const react = hooks();
  const submitted = [];
  let complete;
  const Experience = load('../features/first-open/index.tsx', {
    react,
    './FirstOpen.module.css': { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) },
  }, { window: { setTimeout: () => 1, clearTimeout() {} } });
  const props = {
    stage: 'entry', submittedExpression: null, groundedIdentity: null,
    placeAnchorRef: { current: null }, onGroundingSettled() {}, onWorldSettled() {},
    onSubmit(expression) {
      submitted.push(expression);
      return new Promise((resolve) => { complete = resolve; });
    },
  };
  const render = () => { react.begin(); const tree = Experience(props); react.flush(); return tree; };
  let tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.readOnly, false);
  assert.equal(elements(tree, 'button')[0].props.disabled, true);
  elements(tree, 'textarea')[0].props.onChange({ target: { value: '我住在当前住所' } });
  tree = render();
  assert.equal(elements(tree, 'button')[0].props.disabled, false);
  elements(tree, 'button')[0].props.onClick();
  tree = render();
  assert.equal(elements(tree, 'textarea')[0].props.value, '');
  const entry = elements(tree, 'div').find((element) => element.props.className === 'expressionEntry');
  assert.equal(entry.props['data-entry-hidden'], true, 'initial submission hides the central entry immediately');
  elements(tree, 'textarea')[0].props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.deepEqual(submitted, ['我住在当前住所']);
  complete();
  await tick();
});

test('continuing SSE turns preserve the formed subject, Conversation and camera gate', async () => {
  const react = hooks();
  const home = {
    id: 'home', conversation_id: 'current-conversation', title: '当前住所',
    provenance: 'USER_PROVIDED', geographic_status: 'GROUNDED',
    geographic_identity: '当前住所', geographic_precision: 'PLACE', lng: 104, lat: 31,
  };
  const requests = [];
  let release;
  let fail;
  let failedReread = false;
  let currentProperties = [home];
  let rereads = 0;
  const Runtime = load('../features/first-reality-runtime/index.ts', {
    react, './placeContext': placeContext,
    '@/lib/createClientId': { createClientId() { throw new Error('must keep existing Conversation'); } },
    '@/lib/geographicScaleContract': scale,
    '@/lib/decisionGeographyState': {
      isGroundedDecisionGeography: () => false, isCurrentExpressionReferent: () => false,
      decisionGeographyFingerprint: () => null, shouldApplyObservedDecisionGeography: () => false,
    },
    '@/services/chat': {
      getConversationHistory: async () => ({ messages: [{ role: 'user', content: '我住在当前住所' }] }),
      streamMessage: (options) => {
        requests.push(options);
        return new Promise((resolve, reject) => { release = resolve; fail = reject; });
      },
    },
    '@/services/profile': { getLivingProfile: async () => null },
    '@/services/property': {
      getProperties: async () => {
        rereads++;
        if (failedReread) throw new Error('reread unavailable');
        return currentProperties;
      },
      establishPlaceContext: async () => {},
    },
    '@/services/decisionGeography': { getDecisionGeography: async () => null },
    '@/services/possibleLife': { getPossibleLives: async () => [] },
  }, {
    navigator: {},
    window: {
      setTimeout() { return 1; },
      requestAnimationFrame() { throw new Error('continuation must not reorient camera'); },
      clearTimeout() {},
    },
    console: { ...console, info() {}, error() {} },
  });
  const render = () => { react.begin(); return Runtime({ initialConversationId: home.conversation_id }); };
  render(); react.flush(); await tick();
  let runtime = render();
  assert.equal(runtime.phase, 'formed');
  const identity = runtime.authoritativeReality.identity;
  const center = JSON.stringify(runtime.authoritativeReality.center);
  for (const expression of ['附近吃饭方便吗？', '交通呢？']) {
    const pending = runtime.submit(expression);
    runtime = render(); react.flush();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.firstOpenStage, 'world');
    assert.equal(runtime.isSubmittingExpression, true);
    assert.equal(runtime.authoritativeReality.identity, identity);
    assert.equal(JSON.stringify(runtime.authoritativeReality.center), center);
    const request = requests.at(-1);
    assert.equal(request.conversationId, home.conversation_id);
    assert.equal(request.message, expression);
    request.onWorldStateReady('current-turn');
    request.onWorldConsequenceReady();
    await tick();
    runtime = render(); react.flush();
    assert.equal(runtime.isSubmittingExpression, false, 'authoritative turn reread releases entry before SSE completion');
    // A transient empty reread must not erase the already-admitted World subject.
    currentProperties = [];
    release(); await pending;
    runtime = render(); react.flush();
    assert.equal(runtime.phase, 'formed');
    assert.equal(runtime.isSubmittingExpression, false);
    assert.equal(runtime.authoritativeReality.identity, identity);
    assert.equal(JSON.stringify(runtime.authoritativeReality.center), center);
    assert.equal(runtime.submittedExpression, '我住在当前住所');
    currentProperties = [home];
  }
  assert.equal(requests.length, 2);
  assert.ok(rereads >= 5);
  const failedTurn = runtime.submit('再问一句');
  failedReread = true;
  fail(new Error('transport unavailable'));
  await failedTurn;
  runtime = render();
  assert.equal(runtime.phase, 'formed');
  assert.equal(runtime.isSubmittingExpression, false);
  assert.equal(runtime.authoritativeReality.identity, identity);
});
